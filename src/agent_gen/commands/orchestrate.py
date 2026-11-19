"""`agentfactory-gen orchestrate` commands.

Split out of cli.py (#190); `agent_gen.cli` is the entry point and re-exports these names."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from ..librarian import (
    HARNESS_ROOT,
)
from ._group import _echo, cli
from ._paths import _assert_valid_project_root

_WORKFLOW_SUFFIXES = (".plan.json", ".workflow.json", ".md")  # .plan.json: canonical craft-plan/0.1


def _resolve_workflow_path(spec: str, project_path: Path) -> Path:
    """Resolve a workflow argument: a path, '<agent>/<name>', or a bare name.

    Bare names resolve against .ai/orchestration/workflows/;
    '<agent>/<name>' resolves against that agent's orchestration/workflows/.
    """
    direct = Path(spec)
    if direct.exists():
        return direct

    if "/" in spec:
        agent, _, wf = spec.partition("/")
        base = project_path / HARNESS_ROOT / "agents" / agent / "orchestration" / "workflows"
        candidates = [base / f"{wf}{sfx}" for sfx in _WORKFLOW_SUFFIXES] + [base / wf]
    else:
        base = project_path / HARNESS_ROOT / "orchestration" / "workflows"
        candidates = [base / f"{spec}{sfx}" for sfx in _WORKFLOW_SUFFIXES] + [base / spec]

    for c in candidates:
        if c.exists():
            return c
    raise click.ClickException(
        f"workflow '{spec}' not found (tried the path itself and "
        f"{', '.join(str(c.relative_to(project_path)) for c in candidates)})"
    )


@cli.group("orchestrate")
def orchestrate_group():
    """Orchestrate CLI agents (claude, codex, agy, …) through workflows."""


EXIT_PAUSED = 3  # checkpoint run waiting for approval (not a failure)


@orchestrate_group.command("run")
@click.argument("workflow", required=False)
@click.option("--mode", default=None, help="Override execution mode (sequential, dag, checkpoint).")
@click.option("--dry-run", is_flag=True, default=False, help="Print steps without executing.")
@click.option(
    "--json", "as_json", is_flag=True, default=False, help="Print the RunResult as JSON (machine surface for nesting)."
)
@click.option("--resume", "resume_run", default=None, metavar="RUN_ID", help="Continue a paused checkpoint run.")
@click.option("--yes", "-y", "approve_all", is_flag=True, default=False,
              help="checkpoint mode: approve every step without asking.")  # fmt: skip
@click.option(
    "--project-root", default=".", show_default=True, help="Root of the project whose contract governs the run."
)
def orchestrate_run(
    workflow: str | None,
    mode: str,
    dry_run: bool,
    as_json: bool,
    resume_run: str | None,
    approve_all: bool,
    project_root: str,
):
    """Execute WORKFLOW (path, '<agent>/<name>', or bare name) under the contract.

    checkpoint mode asks before every step after the first (in a terminal) or pauses; a paused run exits with
    code 3 and continues with `--resume RUN_ID`.
    """
    from ..orchestrate import run_workflow

    if bool(workflow) == bool(resume_run):
        raise click.UsageError("Give either WORKFLOW or --resume RUN_ID.")
    project_path = _assert_valid_project_root(project_root)
    wf_path = _resolve_workflow_path(workflow, project_path) if workflow else None

    def confirm(step, result) -> bool:
        if approve_all:
            return True
        if as_json or not sys.stdin.isatty():
            return False  # non-interactive: pause and let a human resume
        what = step.command if step.type == "shell" else (step.prompt[:80] + ("…" if len(step.prompt) > 80 else ""))
        return click.confirm(f"[orchestrate] checkpoint: run step '{step.id}' ({step.type}: {what})?", default=True)

    try:
        result = run_workflow(
            wf_path, project_root=project_path, mode=mode, dry_run=dry_run, confirm=confirm, resume_run=resume_run
        )
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        raise click.ClickException(str(exc)) from exc

    if as_json:
        click.echo(json.dumps(result.to_dict(), indent=2))
    else:
        _echo(f"[orchestrate] workflow '{result.workflow_name}' mode={result.mode}")
        for step_id, status in result.statuses.items():
            _echo(f"  [{status}] {step_id}")
        if result.paused_at:
            _echo(f"[orchestrate] PAUSED before step '{result.paused_at}' (run {result.run_id}).")
            _echo(f"  Review the evidence, then: agentfactory-gen orchestrate run --resume {result.run_id}")
        else:
            _echo(f"[orchestrate] {'OK' if result.ok else 'FAILED'} (run {result.run_id})")

    if result.paused_at:
        sys.exit(EXIT_PAUSED)
    if not result.ok:
        sys.exit(1)


@orchestrate_group.command("validate")
@click.argument("workflow")
@click.option("--project-root", default=".", show_default=True)
def orchestrate_validate(workflow: str, project_root: str):
    """Validate a workflow file and the project contract; exit 1 on issues."""
    from ..orchestrate import load_contract, load_workflow

    project_path = _assert_valid_project_root(project_root)
    wf_path = _resolve_workflow_path(workflow, project_path)

    issues = []
    wf = contract = None
    try:
        wf = load_workflow(wf_path)
        dialect = _dialect_of(wf_path)
        _echo(f"[orchestrate] workflow '{wf.name}' v{wf.version} ({dialect}): {len(wf.steps)} step(s)")
        for s in wf.steps:
            if s.type == "agent" and s.provider not in ("", "cli"):
                _echo(f"[orchestrate] ⚠  step '{s.id}': provider '{s.provider}' is not run by the CLI executor")
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        issues.append(f"workflow: {exc}")

    try:
        contract = load_contract(project_path)
        issues.extend(f"contract: {i}" for i in contract.validate())
    except ValueError as exc:
        issues.append(f"contract: {exc}")

    # Cross-check: every agent/delegate step must resolve to a contract agent
    if wf is not None and contract is not None:
        for s in wf.steps:
            if s.type in ("agent", "delegate"):
                agent_name = s.agent or contract.default_agent
                if agent_name not in contract.agents:
                    issues.append(f"step '{s.id}': unknown agent '{agent_name}'")

    if issues:
        for issue in issues:
            _echo(f"  [invalid] {issue}", err=True)
        sys.exit(1)
    _echo("[orchestrate] ✓ valid")


@orchestrate_group.command("list")
@click.option("--project-root", default=".", show_default=True)
def orchestrate_list(project_root: str):
    """List workflows in the project and in every deployed agent."""
    project_path = _assert_valid_project_root(project_root)
    ai_root = project_path / HARNESS_ROOT

    found: list[tuple[str, Path]] = []
    project_wf = ai_root / "orchestration" / "workflows"
    if project_wf.exists():
        found.extend(
            (p.stem.replace(".workflow", ""), p)
            for p in sorted(project_wf.iterdir())
            if p.name.endswith(_WORKFLOW_SUFFIXES)
        )
    agents_root = ai_root / "agents"
    if agents_root.exists():
        for agent_dir in sorted(agents_root.iterdir()):
            wf_dir = agent_dir / "orchestration" / "workflows"
            if not wf_dir.exists():
                continue
            found.extend(
                (f"{agent_dir.name}/{p.stem.replace('.workflow', '')}", p)
                for p in sorted(wf_dir.iterdir())
                if p.name.endswith(_WORKFLOW_SUFFIXES)
            )

    if not found:
        _echo("[orchestrate] no workflows found — run 'orchestrate init' to scaffold one")
        return
    for name, path in found:
        _echo(f"  {name:<40} {path.relative_to(project_path)}")


@orchestrate_group.command("init")
@click.option("--project-root", default=".", show_default=True)
def orchestrate_init(project_root: str):
    """Scaffold the orchestration contract and an example workflow (idempotent)."""
    from ..orchestrate import CONTRACT_RELPATH, DEFAULT_CONTRACT

    project_path = _assert_valid_project_root(project_root)

    contract_path = project_path / CONTRACT_RELPATH
    if contract_path.exists():
        _echo(f"  [skip] {CONTRACT_RELPATH} (already exists)")
    else:
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        contract_path.write_text(json.dumps(DEFAULT_CONTRACT, indent=2) + "\n", encoding="utf-8")
        _echo(f"  [created] {CONTRACT_RELPATH}")

    example = {
        "name": "example",
        "version": "1.0.0",
        "description": "Two-step example: shell output summarized by an agent.",
        "mode": "sequential",
        "steps": [
            {"id": "collect", "type": "shell", "command": "ls -1", "remediation": "retry", "max_retries": 2},
            {
                "id": "summarize",
                "type": "agent",
                "prompt": "Summarize this file listing in one sentence:\n{steps.collect.stdout}",
                "depends_on": ["collect"],
                "expects": "nonempty",
            },
        ],
    }
    wf_dir = project_path / HARNESS_ROOT / "orchestration" / "workflows"
    wf_path = wf_dir / "example.workflow.json"
    if wf_path.exists():
        _echo(f"  [skip] {wf_path.relative_to(project_path)} (already exists)")
    else:
        wf_dir.mkdir(parents=True, exist_ok=True)
        wf_path.write_text(json.dumps(example, indent=2) + "\n", encoding="utf-8")
        _echo(f"  [created] {wf_path.relative_to(project_path)}")

    _echo("\n[orchestrate] Ready. Try: agentfactory-gen orchestrate run example --dry-run")


def _dialect_of(path: Path) -> str:
    from ..orchestrate.canonical import FORMAT, is_canonical

    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.suffix == ".json" else None
    except (OSError, ValueError):
        data = None
    return FORMAT if is_canonical(data) else "af-workflow"


@orchestrate_group.command("convert")
@click.argument("workflow")
@click.option(
    "--to",
    "target",
    type=click.Choice(["canonical", "af"]),
    default="canonical",
    show_default=True,
    help="canonical = craft-plan/0.1 (CRAFT ADR 0002); af = AgentFactory's .workflow.json format.",
)
@click.option("--output", "-o", default=None, help="Write here instead of stdout.")
@click.option("--project-root", default=".", show_default=True)
def orchestrate_convert(workflow: str, target: str, output: str | None, project_root: str):
    """Convert WORKFLOW between the canonical plan format and AgentFactory's own."""
    from ..orchestrate import load_workflow
    from ..orchestrate.canonical import to_canonical

    project_path = _assert_valid_project_root(project_root)
    wf = load_workflow(_resolve_workflow_path(workflow, project_path))
    try:
        data = to_canonical(wf) if target == "canonical" else wf.to_dict()
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if target == "af":
        data.pop("workflow_id", None)
        data.pop("created_at", None)
        for step in data["steps"]:
            step.pop("seq", None)
    text = json.dumps(data, indent=2) + "\n"
    if output:
        Path(output).write_text(text, encoding="utf-8")
        _echo(f"[orchestrate] wrote {output}")
    else:
        click.echo(text, nl=False)
