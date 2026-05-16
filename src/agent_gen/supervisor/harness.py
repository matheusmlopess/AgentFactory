from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from typing import List, Tuple

from .context import Evidence, PipelineMode, SupervisorContext
from .supervisor import Supervisor
from .workflow import Workflow, WorkflowStep

logger = logging.getLogger(__name__)

_MAX_REMEDIATION_ROUNDS = 2


class HarnessRunner:
    """Executes a Workflow step-by-step, captures evidence, and triggers remediation.

    When a step fails the runner packages the failure as a new draft and
    re-enters the Supervisor pipeline — the same four agents that planned
    the workflow now produce a patch. No special remediation branch exists;
    the path is identical.

    Remediation scope: only the failed step(s) are replaced; successful
    steps upstream are not re-executed.
    """

    def __init__(self, supervisor: Supervisor, dry_run: bool = False) -> None:
        self.supervisor = supervisor
        self.dry_run = dry_run

    def run(
        self, ctx: SupervisorContext, workflow: Workflow
    ) -> Tuple[List[Evidence], Workflow]:
        """Execute the workflow and return all collected evidence + final workflow.

        The returned workflow may differ from the input if remediation replaced
        one or more steps.
        """
        all_evidence: List[Evidence] = []
        step_index = 0

        while step_index < len(workflow.steps):
            step = workflow.steps[step_index]
            ev = self._execute_step(step)
            all_evidence.append(ev)
            ctx.evidence.append(ev)

            if ev.succeeded:
                logger.info("harness: step=%s OK", step.id)
                step_index += 1
                continue

            logger.warning(
                "harness: step=%s FAILED exit=%d stderr=%s",
                step.id,
                ev.exit_code,
                ev.stderr[:120],
            )

            policy = step.remediation_policy
            if policy == "skip":
                logger.info("harness: skipping failed step=%s", step.id)
                step_index += 1
            elif policy == "abort":
                logger.error("harness: aborting workflow at step=%s", step.id)
                break
            elif policy == "retry":
                workflow, step_index = self._retry(
                    ctx, workflow, step, step_index, all_evidence
                )
            else:  # escalate (default)
                workflow, step_index = self._escalate(
                    ctx, workflow, step, step_index
                )

        return all_evidence, workflow

    # ------------------------------------------------------------------
    # Retry handling
    # ------------------------------------------------------------------

    def _retry(
        self,
        ctx: SupervisorContext,
        workflow: Workflow,
        step: WorkflowStep,
        step_index: int,
        all_evidence: List[Evidence],
    ) -> Tuple[Workflow, int]:
        for attempt in range(2, step.max_retries + 1):
            logger.info("harness: retrying step=%s attempt=%d", step.id, attempt)
            ev = self._execute_step(step, attempt=attempt)
            all_evidence.append(ev)
            ctx.evidence.append(ev)
            if ev.succeeded:
                return workflow, step_index + 1
        # Retries exhausted → escalate
        return self._escalate(ctx, workflow, step, step_index)

    # ------------------------------------------------------------------
    # Escalation / remediation
    # ------------------------------------------------------------------

    def _escalate(
        self,
        ctx: SupervisorContext,
        workflow: Workflow,
        failed_step: WorkflowStep,
        step_index: int,
    ) -> Tuple[Workflow, int]:
        if ctx.remediation_round >= _MAX_REMEDIATION_ROUNDS:
            logger.error(
                "harness: max remediation rounds (%d) reached, skipping step=%s",
                _MAX_REMEDIATION_ROUNDS,
                failed_step.id,
            )
            return workflow, step_index + 1

        logger.info(
            "harness: escalating step=%s to supervisor (remediation round %d)",
            failed_step.id,
            ctx.remediation_round + 1,
        )

        # Package the failure as new intake — same path as original planning
        ctx.failed_step_ids = [failed_step.id]
        ctx.draft = _failure_draft(failed_step, ctx.evidence)
        ctx.original_request = (
            f"Remediate failed step: {failed_step.description or failed_step.command}"
        )

        ctx, patch = self.supervisor.remediate(ctx)

        if patch.steps:
            workflow = workflow.patch(patch.steps, [failed_step.id])
            logger.info(
                "harness: workflow patched with %d replacement step(s)", len(patch.steps)
            )
            # Restart from the same index so the new step is executed
            return workflow, step_index

        logger.warning(
            "harness: remediation produced no steps for failed step=%s, skipping",
            failed_step.id,
        )
        return workflow, step_index + 1

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _execute_step(self, step: WorkflowStep, attempt: int = 1) -> Evidence:
        timestamp = datetime.now(timezone.utc).isoformat()
        if self.dry_run:
            logger.info("harness: [dry-run] %s", step.command)
            return Evidence(
                step_id=step.id,
                command=step.command,
                exit_code=0,
                stdout=f"[dry-run] {step.command}",
                stderr="",
                timestamp=timestamp,
                attempt=attempt,
            )
        try:
            result = subprocess.run(
                step.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=step.timeout_seconds,
            )
            return Evidence(
                step_id=step.id,
                command=step.command,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                timestamp=timestamp,
                attempt=attempt,
            )
        except subprocess.TimeoutExpired:
            return Evidence(
                step_id=step.id,
                command=step.command,
                exit_code=124,  # POSIX timeout exit code
                stdout="",
                stderr=f"Command timed out after {step.timeout_seconds}s",
                timestamp=timestamp,
                attempt=attempt,
            )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _failure_draft(step: WorkflowStep, evidence: List[Evidence]) -> str:
    """Build a remediation draft from the most recent failure evidence for a step."""
    failed_ev = next((e for e in reversed(evidence) if e.step_id == step.id), None)
    lines = [f"Failed command: {step.command}"]
    if failed_ev:
        lines.append(f"Exit code: {failed_ev.exit_code}")
        if failed_ev.stderr:
            lines.append(f"Stderr:\n{failed_ev.stderr[:1000]}")
        if failed_ev.stdout:
            lines.append(f"Stdout:\n{failed_ev.stdout[:500]}")
    return "\n".join(lines)
