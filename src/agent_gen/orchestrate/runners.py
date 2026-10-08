"""Step runners — how a WorkflowStep actually executes.

ShellRunner runs `command` through the shell (ported from the supervisor
branch HarnessRunner._execute_step). CliAgentRunner invokes a CLI agent
(claude/codex/agy/…) non-interactively using the invocation template from
the orchestration contract.

Provider-side failure detection lives here (PROVIDER_ERROR_MARKERS) and is
shared with the live test suite: quota exhaustion, outages, and product
retirement must never look like a successful step.
"""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone

from .models import Evidence, EXIT_TIMEOUT, EXIT_EXPECTS_FAILED, WorkflowStep

# Lowercase substrings in agent output that mean the provider (not the
# workflow) failed. Shared with src/tests/test_cli_swap_scenarios.py.
PROVIDER_ERROR_MARKERS = [
    "usage limit",
    "quota",
    "resource_exhausted",
    "rate limit",
    "no longer supported",
    "unsupported_client",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ShellRunner:
    """Execute a shell step. Timeout maps to exit code 124 (POSIX)."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def run(self, step: WorkflowStep, command: str, attempt: int = 1) -> Evidence:
        timestamp = _now()
        if self.dry_run:
            return Evidence(
                step_id=step.id, command=command, exit_code=0,
                stdout=f"[dry-run] {command}", stderr="",
                timestamp=timestamp, attempt=attempt,
            )
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=step.timeout_seconds,
            )
            return Evidence(
                step_id=step.id, command=command, exit_code=result.returncode,
                stdout=result.stdout, stderr=result.stderr,
                timestamp=timestamp, attempt=attempt,
            )
        except subprocess.TimeoutExpired:
            return Evidence(
                step_id=step.id, command=command, exit_code=EXIT_TIMEOUT,
                stdout="", stderr=f"Command timed out after {step.timeout_seconds}s",
                timestamp=timestamp, attempt=attempt,
            )


class CliAgentRunner:
    """Invoke a CLI agent non-interactively per its contract spec.

    spec fields: invocation (list, "{prompt}"/"{workflow}" placeholders),
    stdin ("devnull"), enabled (bool), empty_output_is_failure (bool,
    falls back to the contract-level policy).
    """

    def __init__(self, name: str, spec: dict, policies: dict, dry_run: bool = False):
        self.name = name
        self.spec = spec
        self.policies = policies
        self.dry_run = dry_run

    def _build_command(self, prompt: str) -> list[str]:
        return [
            part.replace("{prompt}", prompt).replace("{workflow}", prompt)
            for part in self.spec["invocation"]
        ]

    def run(self, step: WorkflowStep, prompt: str, attempt: int = 1) -> Evidence:
        timestamp = _now()
        cmd = self._build_command(prompt)
        cmd_display = " ".join(cmd[:-1] + [cmd[-1][:80]])

        if self.dry_run:
            return Evidence(
                step_id=step.id, command=cmd_display, exit_code=0,
                stdout=f"[dry-run] {self.name}: {prompt[:200]}", stderr="",
                timestamp=timestamp, attempt=attempt,
            )

        stdin = subprocess.DEVNULL if self.spec.get("stdin") == "devnull" else None
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=step.timeout_seconds, stdin=stdin,
            )
        except subprocess.TimeoutExpired:
            return Evidence(
                step_id=step.id, command=cmd_display, exit_code=EXIT_TIMEOUT,
                stdout="", stderr=f"{self.name} timed out after {step.timeout_seconds}s",
                timestamp=timestamp, attempt=attempt,
            )
        except FileNotFoundError:
            return Evidence(
                step_id=step.id, command=cmd_display, exit_code=127,
                stdout="", stderr=f"{self.name} binary not found: {cmd[0]}",
                timestamp=timestamp, attempt=attempt,
            )

        exit_code = result.returncode
        stderr = result.stderr

        combined = (result.stdout + result.stderr).lower()
        marker = next((m for m in PROVIDER_ERROR_MARKERS if m in combined), None)
        empty_is_failure = self.spec.get(
            "empty_output_is_failure",
            self.policies.get("empty_output_is_failure", True),
        )

        if exit_code == 0 and marker:
            exit_code = EXIT_EXPECTS_FAILED
            stderr = (stderr + f"\n[orchestrate] provider error detected: '{marker}'").strip()
        elif exit_code == 0 and empty_is_failure and not result.stdout.strip():
            exit_code = EXIT_EXPECTS_FAILED
            stderr = (stderr + f"\n[orchestrate] {self.name} returned empty output "
                               "(quota/outage?) — treated as failure").strip()

        return Evidence(
            step_id=step.id, command=cmd_display, exit_code=exit_code,
            stdout=result.stdout, stderr=stderr,
            timestamp=timestamp, attempt=attempt,
        )
