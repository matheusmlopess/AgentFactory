#!/usr/bin/env python3
# skill-completeness-check.py — Semantic completeness checker for SKILL.md files
# <!-- version: 2.1.1 -->
#
# Usage:
#   python3 .ai/scripts/skill-completeness-check.py [options]
#
# Target (one required):
#   --skill <name>         Global skill: .ai/skills/<name>/SKILL.md
#   --agent <name>         Agent: iterate all SKILL.md under .ai/agents/<name>/skills/
#
# Mode:
#   --mode auto            (default) auto-detect: new-skill if no git baseline, diff otherwise
#   --mode new             Force new-skill self-check (Phase 0 trim)  [pro plan required]
#   --mode diff            Force diff mode — exit 2 if no git baseline
#
# Model:
#   --oracle-model <id>    (default: haiku)
#
#   Model options (an alias or a full model id):
#     haiku    claude-haiku-5-5    Routine checks, CI, pre-commit (default)
#     sonnet   claude-sonnet-5-5   Higher-accuracy trim + atom extraction
#     opus     claude-opus-5-5     Maximum fidelity, complex skills, final review
#
# Claude access (--claude-backend, or AGENTFACTORY_CLAUDE_BACKEND):
#   auto          (default) subscription if available, else API key
#   subscription  Claude Code CLI (`claude -p`) with your Claude subscription:
#                 `claude auth login`, or `claude setup-token` → CLAUDE_CODE_OAUTH_TOKEN.
#                 ANTHROPIC_API_KEY is removed from the child env so usage stays on the plan.
#   api           Anthropic API with ANTHROPIC_API_KEY (optional; needs `pip install anthropic`)
#   --check-access         Print which backend would be used and exit (0 = ok, 2 = none)
#
# Other (unchanged from v1):
#   --old <git-ref>        Git ref for baseline (default: HEAD)
#   --new <path>           Path to trimmed version (--skill mode only; overrides default)
#   --out <path>           JSON report output path
#   --threshold <int>      Explicit threshold override
#   --adapter <name>       Selects threshold + char limit from config
#   --quiet                Suppress terminal output
#
# Plan gating (pro license required):
#   --mode new   (always pro)
#   --mode auto  when the skill has no committed baseline (auto-detected)
#   --agent      (always pro)
#   Set AGENTFACTORY_LICENSE_KEY env var, or store {"license_key": "..."} in .ai/config/user.json
#   Diff mode on committed skills is free.
#
# Exit codes:
#   0 = passed threshold
#   1 = below threshold
#   2 = error (no baseline, API error, file not found)
#   3 = pro plan required
#
# Requires:
#   - Claude Code CLI logged in to a Claude subscription (default), OR
#     ANTHROPIC_API_KEY + the anthropic Python sdk (optional fallback)
#   - git accessible in PATH

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


# ---------------------------------------------------------------------------
# Config + plan helpers
# ---------------------------------------------------------------------------

_CONFIG_PATH = ".ai/config/completeness.json"
_DEFAULT_THRESHOLD = 90

_ADAPTER_CHAR_LIMITS: dict[str, int] = {"claude": 18_000, "codex": 10_000, "gemini": 18_000}
_DEFAULT_CHAR_LIMIT = 18_000

_USER_CONFIG = Path(".ai/config/user.json")
_LICENSE_VALIDATE_URL = "https://api.agentfactory.dev/v1/validate"

_DEFAULT_MODEL = "haiku"


# ---------------------------------------------------------------------------
# Claude access — subscription first (Claude Code CLI), API key optional
# ---------------------------------------------------------------------------

BACKEND_ENV = "AGENTFACTORY_CLAUDE_BACKEND"
BACKENDS = ("auto", "subscription", "api")
_CLAUDE_BIN_ENV = "AGENTFACTORY_CLAUDE_BIN"
_SUBSCRIPTION_TIMEOUT_S = 900

# Aliases resolve to the current generation for the API backend; the Claude Code
# CLI resolves the same aliases itself, so they are passed through unchanged.
MODEL_ALIASES: dict[str, str] = {
    "haiku": "claude-haiku-5-5",
    "sonnet": "claude-sonnet-5-5",
    "opus": "claude-opus-5-5",
}

# Env vars that would switch the Claude Code CLI from the subscription to API billing.
_API_AUTH_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")

ACCESS_HELP = (
    "No Claude access found. Either:\n"
    "  • use your Claude subscription (recommended): install Claude Code and run `claude auth login`,\n"
    "    or on a headless machine `claude setup-token` and export CLAUDE_CODE_OAUTH_TOKEN; or\n"
    "  • use an API key (optional): export ANTHROPIC_API_KEY and `pip install anthropic`."
)


class ClaudeAccessError(RuntimeError):
    """Claude could not be reached or refused the request. The message is user-facing."""


class ClaudeClient(Protocol):
    backend: str

    def complete(self, *, system: str, content: str | list[dict], model: str, max_tokens: int) -> str:
        """Send one system + user turn and return the text reply."""
        ...


def _content_text(content: str | list[dict]) -> str:
    if isinstance(content, str):
        return content
    return "".join(block.get("text", "") for block in content)


def _claude_bin() -> str:
    return os.environ.get(_CLAUDE_BIN_ENV) or "claude"


def _subscription_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in _API_AUTH_VARS}


class SubscriptionClient:
    """Runs `claude -p` with the Claude subscription login (or CLAUDE_CODE_OAUTH_TOKEN).

    No tools, no MCP servers, no session saved, run from an empty temp dir so the
    project's CLAUDE.md is not pulled into the prompt. Never uses --bare: bare mode
    ignores OAuth and would require an API key.
    """

    backend = "subscription"

    def __init__(self, claude_bin: str | None = None, timeout: int = _SUBSCRIPTION_TIMEOUT_S):
        self.claude_bin = claude_bin or _claude_bin()
        self.timeout = timeout

    def complete(self, *, system: str, content: str | list[dict], model: str, max_tokens: int) -> str:
        cmd = [
            self.claude_bin, "-p",
            "--output-format", "json",
            "--model", model,
            "--system-prompt", system,
            "--tools", "",
            "--strict-mcp-config",
            "--no-session-persistence",
        ]
        try:
            with tempfile.TemporaryDirectory(prefix="af-oracle-") as cwd:
                proc = subprocess.run(
                    cmd, input=_content_text(content), capture_output=True, text=True,
                    cwd=cwd, env=_subscription_env(), timeout=self.timeout,
                )
        except FileNotFoundError as e:
            raise ClaudeAccessError(f"Claude Code CLI not found ({self.claude_bin}).") from e
        except subprocess.TimeoutExpired as e:
            raise ClaudeAccessError(f"Claude Code did not answer within {self.timeout}s.") from e
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            detail = (proc.stderr or proc.stdout).strip().splitlines()
            raise ClaudeAccessError(
                "Claude Code failed: " + (detail[-1] if detail else f"exit {proc.returncode}")
            ) from None
        if data.get("is_error") or proc.returncode != 0:
            raise ClaudeAccessError(f"Claude Code error: {data.get('result') or data.get('subtype') or proc.returncode}")
        return str(data.get("result", ""))


class ApiClient:
    """Anthropic API with ANTHROPIC_API_KEY (the optional fallback)."""

    backend = "api"

    def __init__(self, api_key: str):
        import anthropic  # imported lazily: only the API backend needs the SDK

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key)

    def complete(self, *, system: str, content: str | list[dict], model: str, max_tokens: int) -> str:
        anthropic = self._anthropic
        try:
            response = self._client.messages.create(
                model=MODEL_ALIASES.get(model, model),
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": content}],
            )
        except anthropic.AuthenticationError as e:
            raise ClaudeAccessError("Invalid ANTHROPIC_API_KEY.") from e
        except anthropic.BadRequestError as e:
            msg = str(e)
            if "credit balance" in msg or "too low" in msg:
                raise ClaudeAccessError(
                    "Anthropic API account has no credits (console.anthropic.com → Plans & Billing), "
                    "or switch to your subscription: AGENTFACTORY_CLAUDE_BACKEND=subscription."
                ) from e
            raise ClaudeAccessError(f"API error: {e}") from e
        except anthropic.APIConnectionError as e:
            raise ClaudeAccessError("Could not connect to the Anthropic API.") from e
        except anthropic.APIStatusError as e:
            raise ClaudeAccessError(f"API error: {e}") from e
        return "".join(b.text for b in response.content if getattr(b, "type", "") == "text").strip()


def subscription_available(claude_bin: str | None = None) -> bool:
    """True when the Claude Code CLI exists and is signed in to a subscription."""
    claude_bin = claude_bin or _claude_bin()
    if not shutil.which(claude_bin):
        return False
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return True
    try:
        proc = subprocess.run(
            [claude_bin, "auth", "status", "--json"], capture_output=True, text=True,
            env=_subscription_env(), timeout=20,
        )
        status = json.loads(proc.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return False
    # A Console (API-billed) login also reports loggedIn; only count a claude.ai subscription.
    return bool(status.get("loggedIn")) and bool(status.get("subscriptionType") or status.get("authMethod") == "claude.ai")


def api_available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def resolve_backend(preferred: str | None = None) -> str | None:
    """Return "subscription", "api", or None. auto = subscription first, then API key."""
    choice = (preferred or os.environ.get(BACKEND_ENV) or "auto").strip().lower()
    if choice not in BACKENDS:
        raise ClaudeAccessError(f"Unknown Claude backend {choice!r} (use one of: {', '.join(BACKENDS)}).")
    if choice in ("auto", "subscription") and subscription_available():
        return "subscription"
    if choice in ("auto", "api") and api_available():
        return "api"
    return None


def make_client(preferred: str | None = None) -> ClaudeClient:
    """Build the client for the resolved backend, or raise ClaudeAccessError with setup help."""
    backend = resolve_backend(preferred)
    if backend == "subscription":
        return SubscriptionClient()
    if backend == "api":
        return ApiClient(os.environ["ANTHROPIC_API_KEY"])
    choice = (preferred or os.environ.get(BACKEND_ENV) or "auto").strip().lower()
    if choice == "subscription":
        raise ClaudeAccessError("Claude subscription not available: run `claude auth login` "
                                "(or export CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token`).")
    if choice == "api":
        raise ClaudeAccessError("API backend requested but ANTHROPIC_API_KEY is unset or the anthropic SDK is missing.")
    raise ClaudeAccessError(ACCESS_HELP)


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.splitlines()[:-1])
    return raw


def _read_local_key() -> str | None:
    """Read license_key from .ai/config/user.json if present."""
    if _USER_CONFIG.exists():
        try:
            return json.loads(_USER_CONFIG.read_text()).get("license_key")
        except (json.JSONDecodeError, OSError):
            pass
    return None


def load_threshold(adapter: str | None, config_path: str = _CONFIG_PATH) -> int:
    """Return threshold for adapter from config file, or the global default."""
    try:
        with open(config_path) as fh:
            data = json.load(fh)
        block = data.get("completeness", {})
        if adapter:
            return int(block.get("thresholds", {}).get(adapter, block.get("default", _DEFAULT_THRESHOLD)))
        return int(block.get("default", _DEFAULT_THRESHOLD))
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
        return _DEFAULT_THRESHOLD


def load_char_limit(adapter: str | None) -> int:
    """Return char limit for adapter (mirrors librarian.py _FORMAT_REGISTRY values)."""
    return _ADAPTER_CHAR_LIMITS.get(adapter or "", _DEFAULT_CHAR_LIMIT)


def require_plan(minimum: str) -> None:
    """Validate license key against the AgentFactory API. Exit 3 if not authorized."""
    import urllib.request
    import urllib.error

    key = os.environ.get("AGENTFACTORY_LICENSE_KEY") or _read_local_key()
    if not key:
        print(f"\033[31m✗\033[0m This feature requires a {minimum} plan.")
        print('  Set AGENTFACTORY_LICENSE_KEY or store {"license_key": "..."} in .ai/config/user.json')
        print("  Upgrade at https://agentfactory.dev/upgrade")
        sys.exit(3)

    payload = json.dumps({"key": key, "tier": minimum}).encode()
    req = urllib.request.Request(
        _LICENSE_VALIDATE_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode())
            if body.get("valid"):
                return
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        pass

    print(f"\033[31m✗\033[0m Valid {minimum} license key required.")
    print("  Upgrade at https://agentfactory.dev/upgrade")
    sys.exit(3)


# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------

GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

_QUIET = False


def _ok(msg: str) -> None:
    if not _QUIET: print(f"  {GREEN}✓{RESET}  {msg}")


def _warn(msg: str) -> None:
    if not _QUIET: print(f"  {YELLOW}⚠{RESET}  {msg}")


def _fail(msg: str) -> None:
    if not _QUIET: print(f"  {RED}✗{RESET}  {msg}")


def _info(msg: str) -> None:
    if not _QUIET: print(f"  {CYAN}●{RESET}  {msg}")


def _head(msg: str) -> None:
    if not _QUIET: print(f"\n{BOLD}{msg}{RESET}")


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git_show(ref: str, path: str) -> str:
    """Return file content at git ref, or raise RuntimeError."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"git show {ref}:{path} failed: {result.stderr.strip()}")
    return result.stdout


def is_new_skill(ref: str, path: str) -> bool:
    """Return True if path has no committed version at ref (not yet git-tracked)."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return False
    err = result.stderr.lower()
    if "does not exist" in err or "exists on disk" in err or "pathspec" in err:
        return True
    raise RuntimeError(f"git show {ref}:{path} failed: {result.stderr.strip()}")


def find_agent_skills(agent_name: str) -> list[tuple[str, str]]:
    """Return [(skill_name, skill_path)] for all SKILL.md files under an agent."""
    base = Path(f".ai/agents/{agent_name}/skills")
    if not base.exists():
        return []
    return [(p.parent.name, str(p)) for p in sorted(base.rglob("SKILL.md"))]


def extract_version(content: str) -> str:
    for line in content.splitlines():
        if line.strip().startswith("version:"):
            return line.split(":", 1)[1].strip().strip("'\"")
    return "unknown"


# ---------------------------------------------------------------------------
# Claude API calls
# ---------------------------------------------------------------------------

PHASE0_SYSTEM = """\
You are trimming a SKILL.md to fit a character budget while preserving functional behaviour.
Rules:
- Preserve ALL: decision_path, command, error_case, data_table, external_ref, constraint atoms
- Remove first: verbose prose, long examples, repeated explanations
- Preserve YAML frontmatter exactly (version, name, description, triggers)
- Output the trimmed SKILL.md only — no commentary
Target: fit within {char_limit} characters total.
"""

PHASE1_SYSTEM = """\
You are an expert at analysing LLM skill files (SKILL.md). Your job is to extract
all "functional atoms" — the discrete pieces of information that determine how an
LLM will behave when executing this skill.

A functional atom is one of:
- decision_path: a routing table, conditional branch, or step-selection rule
- command: an exact shell/git/gh command the skill instructs the LLM to run
- error_case: a specific failure condition and its required response
- data_table: a lookup table of values (colors, status codes, placeholders, etc.)
- external_ref: a dependency on an external file, path, or tool
- constraint: an explicit rule or prohibition (e.g. "never skip this gate", "always use X")

Output ONLY valid JSON in this exact schema — no commentary:
{
  "atoms": [
    {
      "id": "<slug>",
      "type": "<type>",
      "description": "<one sentence describing what this atom governs>"
    }
  ]
}
"""

PHASE2_SYSTEM = """\
You are verifying that a trimmed LLM skill file preserves all functional behavior
from its original version.

You will receive:
1. A JSON list of "functional atoms" extracted from the original
2. The full text of the trimmed version

For each atom, determine whether it is:
- preserved: fully present with equivalent or better meaning in the trimmed version
- degraded: present but simplified in a way that may affect LLM behavior
- missing: completely absent from the trimmed version

Output ONLY valid JSON in this exact schema — no commentary:
{
  "results": [
    {
      "id": "<atom id>",
      "status": "preserved" | "degraded" | "missing",
      "evidence": "<brief quote from trimmed file, or explanation of absence>"
    }
  ]
}
"""


def phase0_auto_trim(
    client: ClaudeClient, original: str, char_limit: int, model: str
) -> str:
    """Auto-trim a SKILL.md to char_limit. Returns trimmed string — never written to disk."""
    system = PHASE0_SYSTEM.replace("{char_limit}", str(char_limit))
    return client.complete(
        system=system,
        content=f"Trim this SKILL.md to fit within {char_limit} characters:\n\n{original}",
        model=model,
        max_tokens=16_000,
    ).strip()


def phase1_extract_atoms(
    client: ClaudeClient, original: str, model: str
) -> list[dict]:
    """Extract functional atoms from the original SKILL.md (uses ephemeral cache on the API)."""
    raw = client.complete(
        system=PHASE1_SYSTEM,
        content=[
            {
                "type": "text",
                "text": "Extract all functional atoms from this SKILL.md:\n\n" + original,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        model=model,
        max_tokens=16_000,
    )
    return json.loads(_strip_fences(raw))["atoms"]


def phase2_verify_atoms(
    client: ClaudeClient, atoms: list[dict], trimmed: str, model: str
) -> list[dict]:
    """Verify each atom against the trimmed SKILL.md (uses ephemeral cache on the API)."""
    atoms_json = json.dumps({"atoms": atoms}, indent=2)
    raw = client.complete(
        system=PHASE2_SYSTEM,
        content=[
            {
                "type": "text",
                "text": "FUNCTIONAL ATOMS FROM ORIGINAL:\n\n" + atoms_json,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": "\n\nTRIMMED SKILL.md TO VERIFY:\n\n" + trimmed,
            },
        ],
        model=model,
        max_tokens=16_000,
    )
    return json.loads(_strip_fences(raw))["results"]


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------

def compute_score(atoms: list[dict], results: list[dict]) -> tuple[int, dict]:
    """Return (score_pct, summary_dict). degraded counts as 0.5."""
    preserved = sum(1 for r in results if r["status"] == "preserved")
    degraded  = sum(1 for r in results if r["status"] == "degraded")
    missing   = sum(1 for r in results if r["status"] == "missing")
    total = len(atoms)
    if total == 0:
        return 100, {"preserved": 0, "degraded": 0, "missing": 0}
    score = int(round((preserved + 0.5 * degraded) / total * 100))
    return score, {"preserved": preserved, "degraded": degraded, "missing": missing}


# ---------------------------------------------------------------------------
# Atom display
# ---------------------------------------------------------------------------

def print_atoms(atoms: list[dict], results: list[dict]) -> None:
    result_map = {r["id"]: r for r in results}
    by_type: dict[str, list] = {}
    for atom in atoms:
        by_type.setdefault(atom["type"], []).append(atom)

    type_order = [
        "decision_path", "command", "error_case",
        "data_table", "external_ref", "constraint",
    ]
    for t in type_order:
        if t not in by_type:
            continue
        for atom in by_type[t]:
            res = result_map.get(atom["id"])
            status   = res["status"]   if res else "missing"
            evidence = res["evidence"] if res else "not evaluated"
            label = f"[{atom['type']}]"
            desc  = atom["description"]
            if len(desc) > 55:
                desc = desc[:52] + "..."
            line = f"{desc:<55} {label}"
            if status == "preserved":
                _ok(line)
            elif status == "degraded":
                _warn(f"{line}  — {evidence[:60]}")
            else:
                _fail(f"{line}  — {evidence[:60]}")


# ---------------------------------------------------------------------------
# Single-skill check (shared by --skill and --agent modes)
# ---------------------------------------------------------------------------

def run_single_check(
    client: ClaudeClient,
    skill_name: str,
    git_path: str,
    wt_path: str,
    old_ref: str,
    mode: str,
    adapter: str | None,
    threshold: int,
    out_path: str,
    model: str,
) -> tuple[int, dict]:
    """
    Run Phase 0/1/2 for one skill.
    Returns (score, report) on success, or (-1, {}) on error.
    Writes JSON report to out_path.
    """
    char_limit = load_char_limit(adapter)

    # --- Resolve new_skill flag
    if mode == "diff":
        new_skill = False
    elif mode == "new":
        new_skill = True
    else:  # auto
        new_skill = is_new_skill(old_ref, git_path)

    # --- Load original
    if new_skill:
        try:
            with open(wt_path) as f:
                original = f.read()
        except FileNotFoundError:
            print(f"{RED}Error: skill file not found: {wt_path}{RESET}", file=sys.stderr)
            return -1, {}
        old_ref_report = "working_tree"
    else:
        try:
            original = git_show(old_ref, git_path)
        except RuntimeError as e:
            err_msg = str(e)
            lower_msg = err_msg.lower()
            print(f"{RED}Error: {err_msg}{RESET}", file=sys.stderr)
            if "does not exist" in lower_msg or "exists on disk" in lower_msg or "pathspec" in lower_msg:
                print("  Hint: Skill has no committed baseline. Use --mode new for a self-check.", file=sys.stderr)
            return -1, {}
        old_ref_report = old_ref

    # --- Load trimmed (working tree); for new_skill mode this IS the original
    try:
        with open(wt_path) as f:
            trimmed_wt = f.read()
    except FileNotFoundError:
        print(f"{RED}Error: skill file not found: {wt_path}{RESET}", file=sys.stderr)
        return -1, {}

    old_version = extract_version(original)
    new_version = extract_version(trimmed_wt)

    if not _QUIET:
        new_tag = "  [NEW SKILL SELF-CHECK]" if new_skill else ""
        print(f"\n{'═' * 60}")
        print(f"  skill-completeness-check{new_tag}")
        print(f"  Skill  : {skill_name}")
        if new_skill:
            print(f"  Mode   : new skill — auto-trimmed to {char_limit:,} chars")
        else:
            print(f"  Old    : {old_ref} (v{old_version})")
            print(f"  New    : {wt_path} (v{new_version})")
        if adapter:
            print(f"  Adapter: {adapter}   Model: {model}")
        print(f"{'═' * 60}")
        sys.stdout.flush()

    # --- Phase 0 (new skill only): auto-trim in memory
    trimmed_for_check = trimmed_wt
    if new_skill:
        _head(f"Phase 0 — Auto-trimming to {char_limit:,} characters...")
        try:
            trimmed_for_check = phase0_auto_trim(client, original, char_limit, model)
        except Exception as e:
            print(f"{RED}Phase 0 error: {e}{RESET}", file=sys.stderr)
            return -1, {}
        _info(f"Trimmed: {len(original):,} → {len(trimmed_for_check):,} chars")

    # --- Phase 1: extract functional atoms from original
    _head("Phase 1 — Extracting functional atoms" + (" from original..." if not new_skill else "..."))
    try:
        atoms = phase1_extract_atoms(client, original, model)
    except ClaudeAccessError as e:
        print(f"{RED}Error: {e}{RESET}", file=sys.stderr)
        return -1, {}
    except (json.JSONDecodeError, KeyError) as e:
        print(f"{RED}Error parsing Phase 1 response: {e}{RESET}", file=sys.stderr)
        return -1, {}

    by_type: dict[str, int] = {}
    for a in atoms:
        by_type[a["type"]] = by_type.get(a["type"], 0) + 1
    summary_str = ", ".join(f"{v} {k.replace('_', ' ')}s" for k, v in sorted(by_type.items()))
    _info(f"Found {len(atoms)} atoms: {summary_str}")

    # --- Phase 2: verify atoms in trimmed version
    _head("Phase 2 — Checking completeness against trimmed version...")
    try:
        results = phase2_verify_atoms(client, atoms, trimmed_for_check, model)
    except ClaudeAccessError as e:
        print(f"{RED}Error: Phase 2: {e}{RESET}", file=sys.stderr)
        return -1, {}
    except (json.JSONDecodeError, KeyError) as e:
        print(f"{RED}Error parsing Phase 2 response: {e}{RESET}", file=sys.stderr)
        return -1, {}

    print_atoms(atoms, results)

    # --- Score
    score, summary = compute_score(atoms, results)
    print()
    color = GREEN if score >= threshold else (YELLOW if score >= 75 else RED)
    print(
        f"{BOLD}Completeness score: {color}{score}%{RESET}{BOLD}  "
        f"({summary['preserved']} preserved, {summary['degraded']} degraded, "
        f"{summary['missing']} missing){RESET}"
    )

    if new_skill:
        _info("New-skill self-check complete (Phase 0 trim used tokens).")
        _info("Commit first, then re-run to compare against the baseline.")

    # --- Write JSON report
    report_dir = os.path.dirname(out_path)
    if report_dir:
        os.makedirs(report_dir, exist_ok=True)
    report: dict = {
        "skill":        skill_name,
        "mode":         "new_skill" if new_skill else "diff",
        "oracle_model": model,
        "old_ref":      old_ref_report,
        "old_version":  old_version,
        "new_version":  new_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "score":        score,
        "threshold":    threshold,
        "passed":       score >= threshold,
        "summary":      summary,
        "atoms": [
            {
                **atom,
                **next(
                    (r for r in results if r["id"] == atom["id"]),
                    {"status": "missing", "evidence": ""},
                ),
            }
            for atom in atoms
        ],
    }
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    _info(f"Report written to: {out_path}")
    print()

    return score, report


# ---------------------------------------------------------------------------
# Agent summary table
# ---------------------------------------------------------------------------

def summarise_agent(
    results: list[tuple[str, int, bool, str]],
    agent_name: str,
    threshold: int,
) -> int:
    """
    Print agent summary table and return exit code.
    results = [(skill_name, score, passed, mode_tag)]  mode_tag: "new" | "diff"
    """
    passed_count = sum(1 for _, _, p, _ in results)
    total = len(results)
    has_new = any(m == "new" for _, _, _, m in results)

    if not _QUIET:
        W = 62
        tag = "  [NEW SKILL SELF-CHECK]" if has_new else ""
        label = f"  Agent Completeness: {agent_name}{tag}"
        print(f"\n╔{'═' * W}╗")
        print(f"║{label:<{W}}║")
        print(f"╠{'═' * W}╣")
        for skill_name, score, passed, mode_tag in results:
            check    = "✓" if passed else "✗"
            mode_str = "[NEW]" if mode_tag == "new" else "diff"
            row = f"  {skill_name:<22} {score}%  {check}  {mode_str}"
            print(f"║{row:<{W}}║")
        print(f"╚{'═' * W}╝")

        if passed_count == total:
            print(f"\n{GREEN}PASSED: {passed_count}/{total} skills meet threshold ({threshold}%){RESET}")
        else:
            print(f"\n{RED}FAILED: {total - passed_count}/{total} skills below threshold ({threshold}%){RESET}")

    return 0 if passed_count == total else 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Semantic completeness checker for SKILL.md files"
    )

    # Target — mutually exclusive, one required (unless --check-access)
    target = parser.add_mutually_exclusive_group()
    target.add_argument(
        "--skill",
        help="Skill folder name under .ai/skills/ (e.g. git-versioning)",
    )
    target.add_argument(
        "--agent",
        help="Agent name — checks all SKILL.md under .ai/agents/<name>/skills/  [pro]",
    )

    # Mode
    parser.add_argument(
        "--mode",
        choices=["auto", "new", "diff"],
        default="auto",
        help="auto=detect (default), new=self-check [pro], diff=git baseline",
    )

    # Model
    parser.add_argument(
        "--oracle-model",
        default=_DEFAULT_MODEL,
        dest="oracle_model",
        help=f"Claude model for all phases (default: {_DEFAULT_MODEL})",
    )

    # Claude access
    parser.add_argument(
        "--claude-backend",
        choices=list(BACKENDS),
        default=None,
        dest="claude_backend",
        help=f"auto (default: subscription, then API key), subscription, or api. Env: {BACKEND_ENV}",
    )
    parser.add_argument(
        "--check-access",
        action="store_true",
        dest="check_access",
        help="Print which Claude backend would be used and exit (0 = available, 2 = none)",
    )

    # Legacy / unchanged options
    parser.add_argument("--old",       default="HEAD",  help="Git ref for baseline (default: HEAD)")
    parser.add_argument("--new",       default=None,    help="Path to trimmed version (--skill mode only)")
    parser.add_argument("--out",       default=None,    help="JSON report output path")
    parser.add_argument(
        "--threshold", type=int, default=None,
        help="Explicit min %% to exit 0 (overrides config/adapter lookup)",
    )
    parser.add_argument(
        "--adapter", default=None,
        help="Adapter name — selects threshold + char limit from config",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress terminal output (JSON report still written)",
    )

    args = parser.parse_args()

    model   = args.oracle_model
    old_ref = args.old

    # Threshold resolution: explicit → adapter config → config default → 90
    threshold = args.threshold if args.threshold is not None else load_threshold(args.adapter)

    global _QUIET
    _QUIET = args.quiet

    # --- Claude access: subscription first, API key optional
    try:
        client = make_client(args.claude_backend)
    except ClaudeAccessError as e:
        print(f"{RED}Error: {e}{RESET}", file=sys.stderr)
        return 2
    if args.check_access:
        print(f"claude backend: {client.backend}")
        return 0
    if not (args.skill or args.agent):
        parser.error("one of --skill or --agent is required")
    _info(f"Claude backend: {client.backend}  model: {model}")

    # ── Agent mode ────────────────────────────────────────────────────────────
    if args.agent:
        require_plan("pro")

        agent_name = args.agent
        skill_entries = find_agent_skills(agent_name)
        if not skill_entries:
            print(
                f"{RED}Error: No SKILL.md files found under "
                f".ai/agents/{agent_name}/skills/{RESET}",
                file=sys.stderr,
            )
            return 2

        agent_results: list[tuple[str, int, bool, str]] = []
        any_error = False

        for skill_name, skill_path in skill_entries:
            out_path = f".ai/reports/agent-{agent_name}-{skill_name}-completeness.json"
            score, report = run_single_check(
                client=client,
                skill_name=skill_name,
                git_path=skill_path,
                wt_path=skill_path,
                old_ref=old_ref,
                mode=args.mode,
                adapter=args.adapter,
                threshold=threshold,
                out_path=out_path,
                model=model,
            )
            if score >= 0:
                mode_tag = "new" if report.get("mode") == "new_skill" else "diff"
                agent_results.append(
                    (skill_name, score, bool(report.get("passed")), mode_tag)
                )
            else:
                any_error = True

        if not agent_results:
            return 2

        exit_code = summarise_agent(agent_results, agent_name, threshold)
        if any_error:
            print(f"{YELLOW}⚠{RESET}  One or more skills could not be checked (see errors above).")
        return exit_code

    # ── Skill mode ────────────────────────────────────────────────────────────
    skill_name = args.skill
    git_path   = f".ai/skills/{skill_name}/SKILL.md"
    wt_path    = args.new or git_path
    out_path   = args.out or f".ai/reports/skill-{skill_name}-completeness.json"

    # Pro gate: applied before API call
    if args.mode == "new":
        require_plan("pro")
    elif args.mode == "auto":
        # Detect first; require pro only if the skill is uncommitted
        if is_new_skill(old_ref, git_path):
            require_plan("pro")

    score, report = run_single_check(
        client=client,
        skill_name=skill_name,
        git_path=git_path,
        wt_path=wt_path,
        old_ref=old_ref,
        mode=args.mode,
        adapter=args.adapter,
        threshold=threshold,
        out_path=out_path,
        model=model,
    )

    if score < 0:
        return 2

    if report.get("passed"):
        print(f"{GREEN}PASSED: score {score}% meets threshold {threshold}%{RESET}")
        return 0
    print(f"{RED}FAILED: score {score}% is below threshold {threshold}%{RESET}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
