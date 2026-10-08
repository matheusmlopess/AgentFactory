"""Delegate-step planning — a supervisor CLI agent turns a task into substeps.

PR3 scope: send the step prompt + context brief to the contract's
supervisor_agent, parse its JSON reply into WorkflowStep objects (validated,
depth-limited), and splice them into the running workflow. The escalate
remediation policy reuses the same machinery with a failure draft.

PR1 ships this stub so executors can reference a stable interface.
"""
from __future__ import annotations

from .models import Evidence, WorkflowStep


class DelegateUnavailable(NotImplementedError):
    """Raised while the delegate planner is not yet implemented (lands in PR3)."""


def plan_substeps(
    step: WorkflowStep,
    prompt: str,
    contract,
    evidence: list[Evidence],
    depth: int = 0,
) -> list[WorkflowStep]:
    raise DelegateUnavailable(
        "delegate steps and escalate remediation require the delegate planner (PR3); "
        f"step '{step.id}' cannot be delegated yet"
    )


def _failure_draft(step: WorkflowStep, evidence: list[Evidence]) -> str:
    """Build a remediation draft from the most recent failure evidence. (Ported.)"""
    failed_ev = next((e for e in reversed(evidence) if e.step_id == step.id), None)
    lines = [f"Failed step: {step.command or step.prompt}"]
    if failed_ev:
        lines.append(f"Exit code: {failed_ev.exit_code}")
        if failed_ev.stderr:
            lines.append(f"Stderr:\n{failed_ev.stderr[:1000]}")
        if failed_ev.stdout:
            lines.append(f"Stdout:\n{failed_ev.stdout[:500]}")
    return "\n".join(lines)
