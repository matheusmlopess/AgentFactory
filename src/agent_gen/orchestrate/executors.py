"""Execution modes — pluggable via _EXECUTOR_REGISTRY (mirrors _FORMAT_REGISTRY).

SequentialExecutor ports the supervisor-branch HarnessRunner loop:
retry | skip | abort | escalate remediation, timeout evidence, dry-run.
DAG and checkpoint modes land in PR2; plugins register via register_executor().
"""
from __future__ import annotations

import json
import logging
import re

from .contract import OrchestrationContract
from .delegate import DelegateUnavailable, plan_substeps, _failure_draft
from .evidence import NullSink
from .models import (
    EXIT_EXPECTS_FAILED,
    Evidence,
    RunResult,
    StepStatus,
    Workflow,
    WorkflowStep,
)
from .runners import CliAgentRunner, ShellRunner

logger = logging.getLogger(__name__)

EXIT_POLICY_BLOCKED = 126  # step refused by contract policy (shell gate, clearance)


class BaseExecutor:
    """Shared step dispatch + expects-validation + remediation semantics."""

    def __init__(
        self,
        contract: OrchestrationContract,
        dry_run: bool = False,
        sink=None,
    ):
        self.contract = contract
        self.dry_run = dry_run
        self.sink = sink or NullSink()
        self._shell = ShellRunner(dry_run=dry_run)

    # -- to be provided by subclasses ---------------------------------------

    def run(self, workflow: Workflow) -> RunResult:
        raise NotImplementedError

    # -- shared machinery ----------------------------------------------------

    def _execute_step(
        self,
        step: WorkflowStep,
        evidence_by_step: dict[str, Evidence],
        attempt: int = 1,
    ) -> Evidence:
        policies = self.contract.policies

        if step.security_clearance == "blocked":
            return self._refused(step, "security_clearance is 'blocked'", attempt)

        if step.type == "shell":
            if not policies.get("allow_shell_steps", True):
                return self._refused(
                    step, "shell steps disabled by contract policy", attempt
                )
            ev = self._shell.run(step, step.command, attempt=attempt)
        elif step.type == "agent":
            agent_name = step.agent or self.contract.default_agent
            spec = self.contract.agent_spec(agent_name)
            runner = CliAgentRunner(agent_name, spec, policies, dry_run=self.dry_run)
            prompt = step.render_prompt(evidence_by_step)
            ev = runner.run(step, prompt, attempt=attempt)
        else:  # delegate — planning happens in the executor loop, not here
            raise DelegateUnavailable(
                f"step '{step.id}' has type 'delegate' — handled by the executor loop"
            )

        ev = self._check_expects(step, ev)
        self.sink.write_step(ev)
        return ev

    def _refused(self, step: WorkflowStep, reason: str, attempt: int) -> Evidence:
        ev = Evidence(
            step_id=step.id,
            command=step.command or step.prompt[:80],
            exit_code=EXIT_POLICY_BLOCKED,
            stdout="",
            stderr=f"[orchestrate] step refused: {reason}",
            attempt=attempt,
        )
        self.sink.write_step(ev)
        return ev

    @staticmethod
    def _check_expects(step: WorkflowStep, ev: Evidence) -> Evidence:
        """Validate stdout against the step's `expects`; violation → exit 125."""
        if not step.expects or not ev.succeeded:
            return ev
        ok = True
        if step.expects == "nonempty":
            ok = bool(ev.stdout.strip())
        elif step.expects == "json":
            try:
                json.loads(ev.stdout)
            except (ValueError, TypeError):
                ok = False
        elif step.expects.startswith("regex:"):
            ok = re.search(step.expects[len("regex:"):], ev.stdout) is not None
        if not ok:
            ev.exit_code = EXIT_EXPECTS_FAILED
            ev.stderr = (
                ev.stderr + f"\n[orchestrate] output failed expects='{step.expects}'"
            ).strip()
        return ev


class SequentialExecutor(BaseExecutor):
    """Steps run in order; remediation semantics ported from HarnessRunner.run().

    escalate re-plans the failed step through the supervisor agent (PR3);
    until then it aborts the run with a clear message.
    """

    def run(self, workflow: Workflow) -> RunResult:
        result = RunResult(
            workflow_name=workflow.name,
            workflow_id=workflow.workflow_id,
            mode="sequential",
        )
        evidence_by_step: dict[str, Evidence] = {}
        remediation_round = 0
        max_rounds = self.contract.policies.get("max_remediation_rounds", 2)
        step_index = 0

        while step_index < len(workflow.steps):
            step = workflow.steps[step_index]

            if step.type == "delegate":
                try:
                    prompt = step.render_prompt(evidence_by_step)
                    substeps = plan_substeps(
                        step, prompt, self.contract, result.evidence
                    )
                    workflow = _splice(workflow, step, substeps)
                    result.statuses[step.id] = StepStatus.SUCCESS.value
                    step_index += 1
                    continue
                except DelegateUnavailable as exc:
                    logger.error("orchestrate: %s", exc)
                    result.statuses[step.id] = StepStatus.FAILED.value
                    break

            ev = self._execute_step(step, evidence_by_step, attempt=1)
            result.evidence.append(ev)
            evidence_by_step[step.id] = ev

            if ev.succeeded:
                result.statuses[step.id] = StepStatus.SUCCESS.value
                step_index += 1
                continue

            logger.warning(
                "orchestrate: step=%s FAILED exit=%d stderr=%s",
                step.id, ev.exit_code, ev.stderr[:120],
            )
            policy = step.remediation

            if policy == "retry":
                recovered = False
                for attempt in range(2, step.max_retries + 1):
                    ev = self._execute_step(step, evidence_by_step, attempt=attempt)
                    result.evidence.append(ev)
                    evidence_by_step[step.id] = ev
                    if ev.succeeded:
                        recovered = True
                        break
                if recovered:
                    result.statuses[step.id] = StepStatus.SUCCESS.value
                    step_index += 1
                    continue
                policy = "escalate"  # retries exhausted → escalate (ported semantics)

            if policy == "skip":
                result.statuses[step.id] = StepStatus.SKIPPED.value
                step_index += 1
                continue

            if policy == "escalate":
                if remediation_round >= max_rounds:
                    logger.error(
                        "orchestrate: max remediation rounds (%d) reached at step=%s",
                        max_rounds, step.id,
                    )
                    result.statuses[step.id] = StepStatus.FAILED.value
                    break
                remediation_round += 1
                try:
                    draft = _failure_draft(step, result.evidence)
                    replacements = plan_substeps(
                        step, draft, self.contract, result.evidence
                    )
                    if replacements:
                        workflow = workflow.patch(replacements, [step.id])
                        result.statuses.pop(step.id, None)
                        continue  # same index — replacement occupies this slot
                    result.statuses[step.id] = StepStatus.SKIPPED.value
                    step_index += 1
                    continue
                except DelegateUnavailable as exc:
                    logger.error("orchestrate: escalate unavailable — %s", exc)
                    result.statuses[step.id] = StepStatus.FAILED.value
                    break

            # abort (and any unknown fallthrough)
            result.statuses[step.id] = StepStatus.FAILED.value
            break

        # Steps never reached (after abort/escalate-failure) are blocked
        for step in workflow.steps:
            result.statuses.setdefault(step.id, StepStatus.BLOCKED.value)

        result.finished_at = _utcnow()
        result.workflow_snapshot = workflow.to_dict()
        self.sink.finalize(result)
        return result


def _splice(workflow: Workflow, after: WorkflowStep, substeps: list[WorkflowStep]) -> Workflow:
    """Insert delegate-planned substeps immediately after their delegate step."""
    steps: list[WorkflowStep] = []
    for s in workflow.steps:
        steps.append(s)
        if s.id == after.id:
            steps.extend(substeps)
    clone = Workflow(
        name=workflow.name, version=workflow.version,
        description=workflow.description, mode=workflow.mode,
        workflow_id=workflow.workflow_id, created_at=workflow.created_at,
        steps=steps,
    )
    return clone


def _utcnow() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Registry — public plugin point (dag + checkpoint land in PR2)
# ---------------------------------------------------------------------------

_EXECUTOR_REGISTRY: dict[str, type[BaseExecutor]] = {
    "sequential": SequentialExecutor,
}


def register_executor(name: str, cls: type[BaseExecutor]) -> None:
    if not issubclass(cls, BaseExecutor):
        raise TypeError(f"{cls!r} must subclass BaseExecutor")
    _EXECUTOR_REGISTRY[name] = cls


def get_executor(mode: str) -> type[BaseExecutor]:
    try:
        return _EXECUTOR_REGISTRY[mode]
    except KeyError:
        raise ValueError(
            f"unknown execution mode '{mode}' — available: "
            f"{', '.join(sorted(_EXECUTOR_REGISTRY))}"
        ) from None
