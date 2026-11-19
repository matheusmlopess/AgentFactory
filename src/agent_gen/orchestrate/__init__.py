"""agent_gen.orchestrate — CLI-agent orchestration engine.

Public, stable API for programmatic consumers (e.g. agentfactory-harness):

    from agent_gen.orchestrate import load_contract, load_workflow, run_workflow

    contract = load_contract(".")
    result   = run_workflow("path/to/release.workflow.json", project_root=".")
    result.ok, result.statuses, result.evidence

Nothing in this subpackage imports click or cli.py — dependency arrows only
point inward, so the engine can be extracted into a standalone package later.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .contract import (
    CONTRACT_RELPATH,
    DEFAULT_CONTRACT,
    OrchestrationContract,
    load_contract,
)
from .evidence import EvidenceSink, NullSink, find_paused_run
from .executors import (
    BaseExecutor,
    CheckpointExecutor,
    ConfirmFn,
    DagExecutor,
    SequentialExecutor,
    get_executor,
    register_executor,
)
from .models import (
    Evidence,
    RunResult,
    StepStatus,
    Workflow,
    WorkflowStep,
    load_workflow,
    validate_workflow_data,
)
from .runners import DEPTH_ENV, PROVIDER_ERROR_MARKERS, CliAgentRunner, ShellRunner

__all__ = [
    "CONTRACT_RELPATH",
    "DEFAULT_CONTRACT",
    "PROVIDER_ERROR_MARKERS",
    "BaseExecutor",
    "CheckpointExecutor",
    "CliAgentRunner",
    "DagExecutor",
    "Evidence",
    "EvidenceSink",
    "NullSink",
    "OrchestrationContract",
    "RunResult",
    "SequentialExecutor",
    "ShellRunner",
    "StepStatus",
    "Workflow",
    "WorkflowStep",
    "get_executor",
    "load_contract",
    "load_workflow",
    "register_executor",
    "run_workflow",
    "validate_workflow_data",
]

# Nested-orchestration guard: each harness-in-harness level increments this.
_DEPTH_ENV = DEPTH_ENV


def run_workflow(
    workflow: str | Path | Workflow | None = None,
    project_root: str | Path = ".",
    mode: str | None = None,
    dry_run: bool = False,
    persist_evidence: bool = True,
    confirm: ConfirmFn | None = None,
    resume_run: str | None = None,
) -> RunResult:
    """Load (if needed) and execute a workflow under the project's contract.

    checkpoint mode asks *confirm(step, result)* before each step after the first and pauses (writing
    state.json) when it says no or is missing. *resume_run* continues a paused run by its run_id.
    """
    contract = load_contract(project_root)

    depth = int(os.environ.get(_DEPTH_ENV, "0"))
    max_depth = contract.policies.get("max_delegate_depth", 1)
    if depth > max_depth:
        raise RuntimeError(f"nested orchestration depth {depth} exceeds max_delegate_depth={max_depth}")

    state: dict | None = None
    if resume_run:
        run_dir = find_paused_run(project_root, contract.evidence_dir, resume_run)
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        wf = Workflow.from_dict(state["workflow"])
        resolved_mode = state.get("mode", "checkpoint")
        sink: EvidenceSink | NullSink = EvidenceSink.reopen(run_dir)
    else:
        if workflow is None:
            raise ValueError("run_workflow needs a workflow (or resume_run=RUN_ID)")
        wf = workflow if isinstance(workflow, Workflow) else load_workflow(workflow)
        resolved_mode = mode or wf.mode or contract.default_mode
        sink = (
            EvidenceSink(project_root, contract.evidence_dir, wf.name)
            if persist_evidence and not dry_run
            else NullSink()
        )
    executor_cls = get_executor(resolved_mode)
    extra: dict = {}
    if issubclass(executor_cls, CheckpointExecutor):
        extra["confirm"] = confirm
    if state is not None:
        if not issubclass(executor_cls, SequentialExecutor):
            raise ValueError(f"run '{resume_run}' was paused in mode '{resolved_mode}', which cannot resume")
        extra["resume"] = state

    # Steps run inside the project, and child processes (nested harness runs) see the
    # next depth through their own environment; this process's environment is untouched.
    executor = executor_cls(
        contract,
        dry_run=dry_run,
        sink=sink,
        cwd=str(Path(project_root).resolve()),
        env_overrides={_DEPTH_ENV: str(depth + 1)},
        **extra,
    )
    result = executor.run(wf)
    result.mode = resolved_mode
    if state is not None and not result.paused_at and sink.run_dir is not None:
        (Path(sink.run_dir) / "state.json").unlink(missing_ok=True)  # finished: it cannot be resumed again
    return result
