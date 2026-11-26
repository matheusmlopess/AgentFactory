"""Execution modes — pluggable via _EXECUTOR_REGISTRY (mirrors _FORMAT_REGISTRY).

SequentialExecutor ports the supervisor-branch HarnessRunner loop:
retry | skip | abort | escalate remediation, timeout evidence, dry-run.
Also dag and checkpoint modes; plugins register via register_executor().
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import UTC
from pathlib import Path

from .contract import OrchestrationContract
from .delegate import DelegateError, DelegateUnavailable, _failure_draft, plan_substeps
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
        cwd: str | None = None,
        env_overrides: dict[str, str] | None = None,
    ):
        self.contract = contract
        self.dry_run = dry_run
        self.sink = sink or NullSink()
        self.cwd = cwd
        self.env_overrides = env_overrides or {}
        self._shell = ShellRunner(dry_run=dry_run, cwd=cwd, env_overrides=self.env_overrides)

    def _apply_policies(self, workflow: Workflow) -> None:
        for step in workflow.steps:
            step.apply_policy_defaults(self.contract.policies)

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
                return self._refused(step, "shell steps disabled by contract policy", attempt)
            ev = self._shell.run(step, step.command, attempt=attempt)
        elif step.type == "agent" and step.provider not in ("", "cli"):
            return self._refused(
                step, f"provider '{step.provider}' is not run by the CLI executor (use a CLI agent step)", attempt
            )
        elif step.type == "agent":
            agent_name = step.agent or self.contract.default_agent
            spec = self.contract.agent_spec(agent_name)
            runner = CliAgentRunner(
                agent_name,
                spec,
                policies,
                dry_run=self.dry_run,
                cwd=self.cwd,
                env_overrides=self.env_overrides,
            )
            prompt = step.render_prompt(evidence_by_step)
            ev = runner.run(step, prompt, attempt=attempt)
        else:  # delegate — planning happens in the executor loop, not here
            raise DelegateUnavailable(f"step '{step.id}' has type 'delegate' — handled by the executor loop")

        ev = self._check_expects(step, ev)
        self.sink.write_step(ev)
        return ev

    def _run_with_retries(
        self,
        step: WorkflowStep,
        evidence_by_step: dict[str, Evidence],
        result: RunResult,
        lock: threading.Lock | None = None,
    ) -> Evidence:
        """Run *step*, retrying per its policy (max_retries = retries after the first attempt).

        Every attempt's evidence is appended to *result*; the last one is returned.
        """
        attempts = step.max_retries + 1 if step.remediation == "retry" else 1
        ev = None
        for attempt in range(1, attempts + 1):
            ev = self._execute_step(step, evidence_by_step, attempt=attempt)
            if lock:
                with lock:
                    result.evidence.append(ev)
            else:
                result.evidence.append(ev)
            if ev.succeeded:
                break
            logger.warning("orchestrate: step=%s attempt=%d FAILED exit=%d stderr=%s",
                           step.id, attempt, ev.exit_code, ev.stderr[:120])  # fmt: skip
        assert ev is not None  # attempts >= 1
        if not lock:
            evidence_by_step[step.id] = ev
        return ev

    def _planner(self, step: WorkflowStep, result: RunResult):
        """An AskFn that sends a planning prompt to the contract's supervisor agent and records the call."""
        name = self.contract.supervisor_agent
        try:
            spec = self.contract.agent_spec(name)
        except (KeyError, ValueError) as exc:
            raise DelegateUnavailable(f"supervisor_agent '{name}' is not usable: {exc}") from None
        if not spec.get("enabled", True):
            raise DelegateUnavailable(f"supervisor_agent '{name}' is disabled in the contract")
        runner = CliAgentRunner(
            name, spec, self.contract.policies, dry_run=False, cwd=self.cwd, env_overrides=self.env_overrides
        )
        plan_step = WorkflowStep(id=f"{step.id}.plan", type="agent", agent=name, prompt="(planner)")
        plan_step.timeout_seconds = step.timeout_seconds

        def ask(prompt: str, attempt: int) -> Evidence:
            ev = runner.run(plan_step, prompt, attempt=attempt)
            self.sink.write_step(ev)
            result.evidence.append(ev)
            return ev

        return ask

    def _plan(self, step: WorkflowStep, task: str, result: RunResult, depth: int) -> list[WorkflowStep]:
        return plan_substeps(step, task, self.contract, result.evidence, depth=depth, ask=self._planner(step, result))

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
            ok = re.search(step.expects[len("regex:") :], ev.stdout) is not None
        if not ok:
            ev.exit_code = EXIT_EXPECTS_FAILED
            ev.stderr = (ev.stderr + f"\n[orchestrate] output failed expects='{step.expects}'").strip()
        return ev


class SequentialExecutor(BaseExecutor):
    """Steps run in order; remediation semantics ported from HarnessRunner.run().

    escalate re-plans the failed step through the supervisor agent and replaces it with the plan (delegate.py).
    Subclasses can gate each step (`_gate`) and resume from a saved state (`resume=`).
    """

    mode = "sequential"

    def __init__(self, *args, resume: dict | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._resume = resume

    def _gate(self, step: WorkflowStep, index: int, result: RunResult) -> bool:
        """Return False to pause before *step* (checkpoint mode). Sequential never pauses."""
        return True

    def _on_pause(self, workflow: Workflow, index: int, result: RunResult, remediation_round: int) -> None:
        """Called when `_gate` refused a step; checkpoint mode persists state here."""

    def run(self, workflow: Workflow) -> RunResult:
        result = RunResult(workflow_name=workflow.name, workflow_id=workflow.workflow_id, mode=self.mode)
        self._apply_policies(workflow)
        evidence_by_step: dict[str, Evidence] = {}
        remediation_round = 0
        step_index = 0
        if self._resume:
            step_index = self._resume["next_index"]
            remediation_round = self._resume.get("remediation_round", 0)
            result.run_id = self._resume["run_id"]
            result.started_at = self._resume.get("started_at", result.started_at)
            result.statuses = {k: v for k, v in self._resume["statuses"].items() if v != StepStatus.PENDING.value}
            result.evidence = [Evidence(**e) for e in self._resume.get("evidence", [])]
            evidence_by_step = {e.step_id: e for e in result.evidence}
        max_rounds = self.contract.policies.get("max_remediation_rounds", 2)
        resumed_at = step_index if self._resume else None
        depth_of: dict[str, int] = dict((self._resume or {}).get("delegate_depth", {}))  # planned steps → depth
        self._depth_of = depth_of

        while step_index < len(workflow.steps):
            step = workflow.steps[step_index]

            first_of_this_run = step_index == resumed_at or (resumed_at is None and step_index == 0)
            if not first_of_this_run and not self._gate(step, step_index, result):
                result.paused_at = step.id
                self._on_pause(workflow, step_index, result, remediation_round)
                break

            if step.type == "delegate":
                if self.dry_run:
                    logger.info("orchestrate: dry run — delegate step=%s is not planned", step.id)
                    result.statuses[step.id] = StepStatus.SUCCESS.value
                    step_index += 1
                    continue
                depth = depth_of.get(step.id, 0)
                try:
                    substeps = self._plan(step, step.render_prompt(evidence_by_step), result, depth)
                except DelegateError as exc:
                    logger.error("orchestrate: delegate step=%s: %s", step.id, exc)
                    if step.remediation == "skip":
                        result.statuses[step.id] = StepStatus.SKIPPED.value
                        step_index += 1
                        continue
                    result.statuses[step.id] = StepStatus.FAILED.value
                    break
                for sub in substeps:
                    depth_of[sub.id] = depth + 1
                workflow = _splice(workflow, step, substeps)
                result.statuses[step.id] = StepStatus.SUCCESS.value
                step_index += 1
                continue

            ev = self._run_with_retries(step, evidence_by_step, result)
            if ev.succeeded:
                result.statuses[step.id] = StepStatus.SUCCESS.value
                step_index += 1
                continue

            policy = "escalate" if step.remediation == "retry" else step.remediation  # retries exhausted
            if policy == "skip":
                result.statuses[step.id] = StepStatus.SKIPPED.value
                step_index += 1
                continue

            if policy == "escalate":
                if remediation_round >= max_rounds:
                    logger.error(
                        "orchestrate: max remediation rounds (%d) reached at step=%s",
                        max_rounds,
                        step.id,
                    )
                    result.statuses[step.id] = StepStatus.FAILED.value
                    break
                remediation_round += 1
                try:
                    depth = depth_of.get(step.id, 0)
                    replacements = self._plan(step, _failure_draft(step, result.evidence), result, depth)
                    for sub in replacements:
                        depth_of[sub.id] = depth + 1
                    if replacements:
                        workflow = workflow.patch(replacements, [step.id])
                        result.statuses.pop(step.id, None)
                        continue  # same index — replacement occupies this slot
                    result.statuses[step.id] = StepStatus.SKIPPED.value
                    step_index += 1
                    continue
                except DelegateError as exc:
                    logger.error("orchestrate: escalate of step=%s failed — %s", step.id, exc)
                    result.statuses[step.id] = StepStatus.FAILED.value
                    break

            # abort (and any unknown fallthrough)
            result.statuses[step.id] = StepStatus.FAILED.value
            break

        # Steps never reached: pending while paused, blocked after a failure.
        leftover = StepStatus.PENDING.value if result.paused_at else StepStatus.BLOCKED.value
        for step in workflow.steps:
            result.statuses.setdefault(step.id, leftover)

        result.finished_at = _utcnow()
        result.workflow_snapshot = workflow.to_dict()
        self.sink.finalize(result)
        return result


ConfirmFn = Callable[[WorkflowStep, RunResult], bool]


class CheckpointExecutor(SequentialExecutor):
    """Sequential with a human gate before every step after the first (PR2).

    `confirm(step, result)` decides; without one (non-interactive) the run pauses at the first gate. A paused run
    writes `state.json` next to its evidence; `run_workflow(resume_run=RUN_ID)` continues it, and the resumed step
    runs without asking again (resuming is the approval).
    """

    mode = "checkpoint"

    def __init__(self, *args, confirm: ConfirmFn | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._confirm = confirm

    def _gate(self, step: WorkflowStep, index: int, result: RunResult) -> bool:
        if self.dry_run:
            return True
        return bool(self._confirm and self._confirm(step, result))

    def _on_pause(self, workflow: Workflow, index: int, result: RunResult, remediation_round: int) -> None:
        run_dir = getattr(self.sink, "run_dir", None)
        if run_dir is None:
            return
        state = {
            "run_id": result.run_id,
            "mode": self.mode,
            "started_at": result.started_at,
            "next_index": index,
            "remediation_round": remediation_round,
            "delegate_depth": dict(getattr(self, "_depth_of", {})),
            "workflow": workflow.to_dict(),
            "statuses": dict(result.statuses),
            "evidence": [e.to_dict() for e in result.evidence],
        }
        write_state(Path(run_dir), state)


def write_state(run_dir: Path, state: dict) -> Path:
    """Persist a paused run's state atomically under a file lock (resume may race a second `run --resume`)."""
    from filelock import FileLock

    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "state.json"
    with FileLock(str(path) + ".lock", timeout=10):
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp.replace(path)
    return path


class DagExecutor(BaseExecutor):
    """Run steps as soon as their `depends_on` are done, up to `max_parallel` at a time (PR2).

    A failed (or blocked) dependency blocks its dependents. `skip` lets dependents run, `abort` stops scheduling
    new steps, and retries behave as in sequential mode. Planning does not happen mid-graph: delegate steps need
    sequential or checkpoint mode, and an `escalate` step that still fails is marked failed.
    """

    mode = "dag"

    def run(self, workflow: Workflow) -> RunResult:
        delegates = [s.id for s in workflow.steps if s.type == "delegate"]
        if delegates:
            raise ValueError(f"dag mode cannot run delegate steps {delegates}: use sequential or checkpoint")
        workflow.topological_order()  # cycle check
        self._apply_policies(workflow)
        result = RunResult(workflow_name=workflow.name, workflow_id=workflow.workflow_id, mode=self.mode)
        evidence_by_step: dict[str, Evidence] = {}
        lock = threading.Lock()
        done_ok: set[str] = set()
        statuses: dict[str, str] = {}
        pending = {s.id: s for s in workflow.steps}
        abort = False
        workers = max(1, int(self.contract.policies.get("max_parallel", 4)))

        def task(step: WorkflowStep) -> Evidence:
            with lock:
                inputs = dict(evidence_by_step)  # dependencies are complete; snapshot for templating
            return self._run_with_retries(step, inputs, result, lock=lock)

        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="orch-dag") as pool:
            running: dict[Future, WorkflowStep] = {}
            while pending or running:
                # Block steps whose dependency failed; start steps whose dependencies all succeeded/skipped.
                progressed = True
                while progressed:
                    progressed = False
                    for sid, step in list(pending.items()):
                        if any(statuses.get(d) in (StepStatus.FAILED.value, StepStatus.BLOCKED.value)
                               for d in step.depends_on):  # fmt: skip
                            statuses[sid] = StepStatus.BLOCKED.value
                            del pending[sid]
                            progressed = True
                        elif not abort and len(running) < workers and all(d in done_ok for d in step.depends_on):
                            # Never queue more than there are workers, so abort really stops new work.
                            running[pool.submit(task, step)] = step
                            del pending[sid]
                            progressed = True
                if not running:
                    break  # aborted, or everything left is blocked
                finished, _ = wait(running, return_when=FIRST_COMPLETED)
                for fut in finished:
                    step = running.pop(fut)
                    ev = fut.result()
                    with lock:
                        evidence_by_step[step.id] = ev
                    if ev.succeeded:
                        statuses[step.id] = StepStatus.SUCCESS.value
                        done_ok.add(step.id)
                    elif step.remediation == "skip":
                        statuses[step.id] = StepStatus.SKIPPED.value
                        done_ok.add(step.id)
                    else:
                        if step.remediation in ("retry", "escalate"):
                            logger.error(
                                "orchestrate: step=%s failed; dag mode does not re-plan (use sequential)", step.id
                            )
                        statuses[step.id] = StepStatus.FAILED.value
                        abort = abort or step.remediation == "abort"

        for sid in pending:
            statuses[sid] = StepStatus.BLOCKED.value
        result.statuses = {s.id: statuses.get(s.id, StepStatus.BLOCKED.value) for s in workflow.steps}
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
        name=workflow.name,
        version=workflow.version,
        description=workflow.description,
        mode=workflow.mode,
        workflow_id=workflow.workflow_id,
        created_at=workflow.created_at,
        steps=steps,
    )
    return clone


def _utcnow() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Registry — public plugin point
# ---------------------------------------------------------------------------

_EXECUTOR_REGISTRY: dict[str, type[BaseExecutor]] = {
    "sequential": SequentialExecutor,
    "checkpoint": CheckpointExecutor,
    "dag": DagExecutor,
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
            f"unknown execution mode '{mode}' — available: {', '.join(sorted(_EXECUTOR_REGISTRY))}"
        ) from None
