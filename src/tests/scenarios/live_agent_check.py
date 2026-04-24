#!/usr/bin/env python3
"""
live_agent_check.py — Tier 2 live CLI agent harness verification.

Initializes a fresh AgentFactory project, adds a recognizable skill,
then invokes the target CLI agent and asserts it acknowledges the harness.

Usage:
    python3 src/tests/scenarios/live_agent_check.py claude
    python3 src/tests/scenarios/live_agent_check.py codex
    python3 src/tests/scenarios/live_agent_check.py gemini

Exit codes:
    0  — PASS or SKIP (CLI not installed)
    1  — FAIL (agent response missing expected keywords)
    2  — ERROR (invocation failed)
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_PROBE_PROMPT = (
    "What harness root does this project use? "
    "What adapter are you running in? "
    "Name one available skill."
)

# CLI invocation per adapter. Flags are best-effort — verify for your version.
_CLI_INVOCATION = {
    "claude": ["claude", "--print", _PROBE_PROMPT],
    "codex":  ["codex",  "exec", "--skip-git-repo-check", _PROBE_PROMPT],
    "gemini": ["gemini", "--prompt", _PROBE_PROMPT],
}

# Keywords a well-briefed agent should mention (lowercase, any substring match).
_EXPECTED_KEYWORDS = {
    "claude": [".ai", "harness"],
    "codex":  [".ai", "harness"],
    "gemini": [".ai", "harness"],
}

_SUPPORTED = list(_CLI_INVOCATION.keys())


def _init_project(proj: Path, adapter: str) -> None:
    from click.testing import CliRunner
    from agent_gen.cli import cli
    from agent_gen.librarian import HARNESS_ROOT

    runner = CliRunner()
    r = runner.invoke(cli, ["init", "--primary", adapter, "--project-root", str(proj)])
    if r.exit_code != 0:
        raise RuntimeError(f"agentfactory-gen init failed:\n{r.output}")

    # Add a recognisable skill
    skill_dir = proj / HARNESS_ROOT / "skills" / "deploy-pipeline"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "skill-manifest.json").write_text(
        json.dumps({
            "name": "deploy-pipeline",
            "description": "Automates the CI/CD deploy pipeline end-to-end",
            "triggers": "when deploying to production",
            "input": "",
        }),
        encoding="utf-8",
    )

    r2 = runner.invoke(cli, ["brief", "--project-root", str(proj)])
    if r2.exit_code != 0:
        raise RuntimeError(f"agentfactory-gen brief failed:\n{r2.output}")


def check(adapter: str) -> int:
    if adapter not in _SUPPORTED:
        print(f"ERROR: unknown adapter '{adapter}'. Choose from: {_SUPPORTED}")
        return 2

    if not shutil.which(adapter):
        print(f"SKIP: '{adapter}' CLI not installed on PATH")
        return 0

    with tempfile.TemporaryDirectory(prefix=f"af_live_{adapter}_") as tmp:
        proj = Path(tmp) / "proj"
        proj.mkdir()

        print(f"[setup] Initializing project at {proj} with primary={adapter} ...")
        try:
            _init_project(proj, adapter)
        except RuntimeError as exc:
            print(f"ERROR: {exc}")
            return 2

        print(f"[invoke] Running: {' '.join(_CLI_INVOCATION[adapter])}")
        try:
            proc = subprocess.run(
                _CLI_INVOCATION[adapter],
                cwd=str(proj),
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            print(f"ERROR: {adapter} CLI timed out after 120s")
            return 2
        except FileNotFoundError:
            print(f"ERROR: {adapter} binary not found (PATH issue?)")
            return 2

        response = (proc.stdout + proc.stderr).lower()
        print(f"[response] exit={proc.returncode}, len={len(response)}")
        print(f"[response excerpt]\n{response[:600]}\n{'─'*60}")

        missing = [kw for kw in _EXPECTED_KEYWORDS[adapter] if kw.lower() not in response]
        if missing:
            print(f"FAIL: response missing keywords: {missing}")
            return 1

        print(f"PASS: {adapter} acknowledged the AgentFactory harness")
        return 0


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    sys.exit(check(sys.argv[1]))
