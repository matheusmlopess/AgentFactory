#!/usr/bin/env python3
# skill-completeness-check.py — Semantic completeness checker for SKILL.md files
# <!-- version: 1.0.0 -->
#
# Usage:
#   python3 .ai/scripts/skill-completeness-check.py --skill <name> [options]
#
# Options:
#   --skill <name>     Skill folder name under .ai/skills/ (e.g. diff-visualizer)
#   --old <git-ref>    Git ref for original (default: HEAD)
#   --new <path>       Path to trimmed version (default: .ai/skills/<name>/SKILL.md)
#   --out <path>       JSON report path (default: .ai/reports/skill-<name>-completeness.json)
#   --threshold <int>  Minimum completeness % to exit 0 (default: 90)
#
# Requires:
#   - ANTHROPIC_API_KEY environment variable
#   - anthropic Python SDK: pip install anthropic
#   - git accessible in PATH

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import anthropic

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

def _ok(msg):
    if not _QUIET: print(f"  {GREEN}✓{RESET}  {msg}")
def _warn(msg):
    if not _QUIET: print(f"  {YELLOW}⚠{RESET}  {msg}")
def _fail(msg):
    if not _QUIET: print(f"  {RED}✗{RESET}  {msg}")
def _info(msg):
    if not _QUIET: print(f"  {CYAN}●{RESET}  {msg}")
def _head(msg):
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

def extract_version(content: str) -> str:
    for line in content.splitlines():
        if line.strip().startswith("version:"):
            return line.split(":", 1)[1].strip().strip("'\"")
    return "unknown"

# ---------------------------------------------------------------------------
# Claude API calls
# ---------------------------------------------------------------------------

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


def phase1_extract_atoms(client: anthropic.Anthropic, original: str) -> list[dict]:
    """Extract functional atoms from the original SKILL.md."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=PHASE1_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Extract all functional atoms from this SKILL.md:\n\n" + original,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ],
    )
    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.splitlines()[:-1])
    return json.loads(raw)["atoms"]


def phase2_verify_atoms(
    client: anthropic.Anthropic, atoms: list[dict], trimmed: str
) -> list[dict]:
    """Verify each atom against the trimmed SKILL.md."""
    atoms_json = json.dumps({"atoms": atoms}, indent=2)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8192,
        system=PHASE2_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": [
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
            }
        ],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.splitlines()[:-1])
    return json.loads(raw)["results"]


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------

def compute_score(atoms: list[dict], results: list[dict]) -> tuple[int, dict]:
    """Return (score_pct, summary_dict)."""
    status_map = {r["id"]: r["status"] for r in results}
    preserved = sum(1 for r in results if r["status"] == "preserved")
    degraded  = sum(1 for r in results if r["status"] == "degraded")
    missing   = sum(1 for r in results if r["status"] == "missing")
    total = len(atoms)
    if total == 0:
        return 100, {"preserved": 0, "degraded": 0, "missing": 0}
    # degraded counts as 0.5
    score = int(round((preserved + 0.5 * degraded) / total * 100))
    return score, {"preserved": preserved, "degraded": degraded, "missing": missing}


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------

def print_atoms(atoms: list[dict], results: list[dict]) -> None:
    result_map = {r["id"]: r for r in results}
    # Group by type
    by_type: dict[str, list] = {}
    for atom in atoms:
        by_type.setdefault(atom["type"], []).append(atom)

    type_order = ["decision_path", "command", "error_case", "data_table", "external_ref", "constraint"]
    for t in type_order:
        if t not in by_type:
            continue
        for atom in by_type[t]:
            res = result_map.get(atom["id"])
            status = res["status"] if res else "missing"
            evidence = res["evidence"] if res else "not evaluated"
            label = f"[{atom['type']}]"
            desc = atom["description"]
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
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Semantic completeness checker for SKILL.md files"
    )
    parser.add_argument("--skill",     required=True, help="Skill folder name under .ai/skills/")
    parser.add_argument("--old",       default="HEAD",  help="Git ref for original (default: HEAD)")
    parser.add_argument("--new",       default=None,    help="Path to trimmed version")
    parser.add_argument("--out",       default=None,    help="JSON report output path")
    parser.add_argument("--threshold", type=int, default=90, help="Min % to exit 0 (default: 90)")
    parser.add_argument("--quiet", action="store_true", help="Suppress terminal output (JSON report still written)")
    args = parser.parse_args()

    skill_name   = args.skill
    old_ref      = args.old
    new_path     = args.new or f".ai/skills/{skill_name}/SKILL.md"
    out_path     = args.out or f".ai/reports/skill-{skill_name}-completeness.json"
    threshold    = args.threshold
    skill_git    = f".ai/skills/{skill_name}/SKILL.md"

    global _QUIET
    _QUIET = args.quiet

    # --- API key check
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(f"{RED}Error: ANTHROPIC_API_KEY environment variable not set.{RESET}", file=sys.stderr)
        return 2

    # --- Read files
    try:
        original = git_show(old_ref, skill_git)
    except RuntimeError as e:
        print(f"{RED}Error: {e}{RESET}", file=sys.stderr)
        return 2

    try:
        with open(new_path) as f:
            trimmed = f.read()
    except FileNotFoundError:
        print(f"{RED}Error: trimmed file not found: {new_path}{RESET}", file=sys.stderr)
        return 2

    old_version = extract_version(original)
    new_version = extract_version(trimmed)

    if not _QUIET:
        print(f"\n{'═' * 55}")
        print(f"  skill-completeness-check")
        print(f"  Skill : {skill_name}")
        print(f"  Old   : {old_ref} (v{old_version})")
        print(f"  New   : {new_path} (v{new_version})")
        print(f"{'═' * 55}")
        sys.stdout.flush()

    client = anthropic.Anthropic(api_key=api_key)

    # --- Phase 1
    _head(f"Phase 1 — Extracting functional atoms from {old_ref}...")
    try:
        atoms = phase1_extract_atoms(client, original)
    except anthropic.BadRequestError as e:
        msg = str(e)
        if "credit balance" in msg or "too low" in msg:
            print(f"{RED}Error: Anthropic account has no credits.{RESET}", file=sys.stderr)
            print(f"  → Add credits at console.anthropic.com → Plans & Billing", file=sys.stderr)
        else:
            print(f"{RED}API error: {e}{RESET}", file=sys.stderr)
        return 2
    except anthropic.AuthenticationError:
        print(f"{RED}Error: Invalid ANTHROPIC_API_KEY.{RESET}", file=sys.stderr)
        return 2
    except anthropic.APIConnectionError:
        print(f"{RED}Error: Could not connect to Anthropic API.{RESET}", file=sys.stderr)
        return 2
    except (json.JSONDecodeError, KeyError) as e:
        print(f"{RED}Error parsing Phase 1 response: {e}{RESET}", file=sys.stderr)
        return 2

    by_type: dict[str, int] = {}
    for a in atoms:
        by_type[a["type"]] = by_type.get(a["type"], 0) + 1
    summary_str = ", ".join(f"{v} {k.replace('_', ' ')}s" for k, v in sorted(by_type.items()))
    _info(f"Found {len(atoms)} atoms: {summary_str}")

    # --- Phase 2
    _head("Phase 2 — Checking completeness against trimmed version...")
    try:
        results = phase2_verify_atoms(client, atoms, trimmed)
    except (anthropic.BadRequestError, anthropic.AuthenticationError, anthropic.APIConnectionError) as e:
        print(f"{RED}API error in Phase 2: {e}{RESET}", file=sys.stderr)
        return 2
    except (json.JSONDecodeError, KeyError) as e:
        print(f"{RED}Error parsing Phase 2 response: {e}{RESET}", file=sys.stderr)
        return 2

    print_atoms(atoms, results)

    # --- Score
    score, summary = compute_score(atoms, results)
    print()
    color = GREEN if score >= threshold else (YELLOW if score >= 75 else RED)
    print(f"{BOLD}Completeness score: {color}{score}%{RESET}{BOLD}  "
          f"({summary['preserved']} preserved, {summary['degraded']} degraded, "
          f"{summary['missing']} missing){RESET}")

    # --- Write JSON report
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    report = {
        "skill":       skill_name,
        "old_ref":     old_ref,
        "old_version": old_version,
        "new_version": new_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "score":       score,
        "threshold":   threshold,
        "passed":      score >= threshold,
        "summary":     summary,
        "atoms": [
            {**atom, **next((r for r in results if r["id"] == atom["id"]), {"status": "missing", "evidence": ""})}
            for atom in atoms
        ],
    }
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    _info(f"Report written to: {out_path}")
    print()

    if score < threshold:
        print(f"{RED}FAILED: score {score}% is below threshold {threshold}%{RESET}")
        return 1
    print(f"{GREEN}PASSED: score {score}% meets threshold {threshold}%{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
