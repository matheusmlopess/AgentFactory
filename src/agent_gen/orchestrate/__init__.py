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

import os
from pathlib import Path

from .contract import (
    CONTRACT_RELPATH,
    DEFAULT_CONTRACT,
    OrchestrationContract,
    load_contract,
)
from .evidence import EvidenceSink, NullSink
from .executors import (
    BaseExecutor,
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
from .runners import PROVIDER_ERROR_MARKERS, CliAgentRunner, ShellRunner

__all__ = [
    "CONTRACT_RELPATH",
    "DEFAULT_CONTRACT",
    "OrchestrationContract",
    "load_contract",
    "EvidenceSink",
    "NullSink",
    "BaseExecutor",
    "SequentialExecutor",
    "get_executor",
    "register_executor",
    "Evidence",
    "RunResult",
    "StepStatus",
    "Workflow",
    "WorkflowStep",
    "load_workflow",
    "validate_workflow_data",
    "PROVIDER_ERROR_MARKERS",
    "CliAgentRunner",
    "ShellRunner",
    "run_workflow",
]

# Nested-orchestration guard: each harness-in-harness level increments this.
_DEPTH_ENV = "AGENTFACTORY_ORCH_DEPTH"


def run_workflow(
    workflow: str | Path | Workflow,
    project_root: str | Path = ".",
    mode: str | None = None,
    dry_run: bool = False,
    persist_evidence: bool = True,
) -> RunResult:
    """Load (if needed) and execute a workflow under the project's contract."""
    contract = load_contract(project_root)

    depth = int(os.environ.get(_DEPTH_ENV, "0"))
    max_depth = contract.policies.get("max_delegate_depth", 1)
    if depth > max_depth:
        raise RuntimeError(
            f"nested orchestration depth {depth} exceeds max_delegate_depth={max_depth}"
        )

    wf = workflow if isinstance(workflow, Workflow) else load_workflow(workflow)
    resolved_mode = mode or wf.mode or contract.default_mode
    executor_cls = get_executor(resolved_mode)

    sink = (
        EvidenceSink(project_root, contract.evidence_dir, wf.name)
        if persist_evidence and not dry_run
        else NullSink()
    )

    executor = executor_cls(contract, dry_run=dry_run, sink=sink)
    os.environ[_DEPTH_ENV] = str(depth + 1)
    try:
        result = executor.run(wf)
    finally:
        os.environ[_DEPTH_ENV] = str(depth)
    result.mode = resolved_mode
    return result
