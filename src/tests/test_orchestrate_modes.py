"""#195: dag and checkpoint execution modes."""

import json
import time
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_gen.cli import cli
from agent_gen.orchestrate import Workflow, run_workflow
from agent_gen.orchestrate.models import WorkflowStep


def _wf(*steps, mode):
    return Workflow(name="m", mode=mode, steps=list(steps))


def _sh(id, command, **kw):
    return WorkflowStep(id=id, type="shell", command=command, **kw)


def _set_policy(project: Path, **policies):
    path = project / ".ai" / "config" / "orchestration.json"
    data = json.loads(path.read_text())
    data.setdefault("policies", {}).update(policies)
    path.write_text(json.dumps(data))


# ---------------------------------------------------------------- dag


@pytest.mark.parametrize("workers,min_s,max_s", [(2, 0.0, 0.75), (1, 0.8, 5.0)])
def test_dag_runs_independent_steps_in_parallel(orch_project, workers, min_s, max_s):
    _set_policy(orch_project, max_parallel=workers)
    wf = _wf(_sh("a", "sleep 0.45"), _sh("b", "sleep 0.45"), mode="dag")
    start = time.monotonic()
    result = run_workflow(wf, project_root=orch_project)
    elapsed = time.monotonic() - start
    assert result.ok, result.statuses
    assert min_s <= elapsed < max_s, elapsed


def test_dag_respects_dependencies(orch_project, tmp_path):
    marker = tmp_path / "order"
    wf = _wf(
        _sh("join", f"cat {marker}", depends_on=["first", "second"]),
        _sh("first", f"sleep 0.2; echo first >> {marker}"),
        _sh("second", f"echo second >> {marker}"),
        mode="dag",
    )
    result = run_workflow(wf, project_root=orch_project)
    assert result.ok, (result.statuses, [e.stderr for e in result.evidence])
    join = next(e for e in result.evidence if e.step_id == "join")
    assert sorted(join.stdout.split()) == ["first", "second"]  # both dependencies finished before join ran
    assert list(result.statuses) == ["join", "first", "second"]  # reported in workflow order


def test_dag_failed_dependency_blocks_dependents_only(orch_project):
    wf = _wf(
        _sh("bad", "exit 1", remediation="escalate"),
        _sh("after-bad", "echo never", depends_on=["bad"]),
        _sh("independent", "echo still runs"),
        mode="dag",
    )
    result = run_workflow(wf, project_root=orch_project)
    assert result.statuses == {"bad": "failed", "after-bad": "blocked", "independent": "success"}
    assert not result.ok


def test_dag_skip_lets_dependents_run(orch_project):
    wf = _wf(_sh("flaky", "exit 1", remediation="skip"), _sh("next", "echo ok", depends_on=["flaky"]), mode="dag")
    assert run_workflow(wf, project_root=orch_project).statuses == {"flaky": "skipped", "next": "success"}


def test_dag_abort_stops_scheduling(orch_project):
    _set_policy(orch_project, max_parallel=1)
    wf = _wf(_sh("stop", "exit 1", remediation="abort"), _sh("later", "echo no"), mode="dag")
    assert run_workflow(wf, project_root=orch_project).statuses == {"stop": "failed", "later": "blocked"}


def test_dag_retries(orch_project, tmp_path):
    flag = tmp_path / "flag"
    cmd = f"test -f {flag} && echo ok || (touch {flag}; exit 1)"
    result = run_workflow(_wf(_sh("r", cmd, remediation="retry", max_retries=1), mode="dag"), project_root=orch_project)
    assert result.ok and [e.attempt for e in result.evidence] == [1, 2]


def test_dag_rejects_delegate_steps(orch_project):
    wf = _wf(WorkflowStep(id="d", type="delegate", prompt="plan it"), mode="dag")
    with pytest.raises(ValueError, match="delegate"):
        run_workflow(wf, project_root=orch_project)


def test_cycles_are_rejected_at_load_time():
    with pytest.raises(ValueError, match="cycle"):
        Workflow.from_dict(
            {
                "name": "c",
                "steps": [
                    {"id": "a", "command": "true", "depends_on": ["b"]},
                    {"id": "b", "command": "true", "depends_on": ["a"]},
                ],
            }
        )


# ---------------------------------------------------------------- checkpoint


def _three(mode="checkpoint"):
    return _wf(_sh("one", "echo 1"), _sh("two", "echo 2"), _sh("three", "echo 3"), mode=mode)


def test_checkpoint_pauses_then_resumes_to_completion(orch_project):
    first = run_workflow(_three(), project_root=orch_project)  # no confirm callback: pause at the first gate
    assert first.paused_at == "two" and not first.ok
    assert first.statuses == {"one": "success", "two": "pending", "three": "pending"}
    runs = list((orch_project / ".ai" / "memory" / "orchestration-runs").glob("*/state.json"))
    assert len(runs) == 1

    second = run_workflow(project_root=orch_project, resume_run=first.run_id)  # resuming approves "two"
    assert second.run_id == first.run_id and second.paused_at == "three"
    assert second.statuses == {"one": "success", "two": "success", "three": "pending"}

    third = run_workflow(project_root=orch_project, resume_run=first.run_id, confirm=lambda step, res: True)
    assert third.ok and third.paused_at is None
    assert [e.step_id for e in third.evidence] == ["one", "two", "three"]
    assert not runs[0].exists()  # finished runs cannot be resumed again
    with pytest.raises(FileNotFoundError, match="no paused run"):
        run_workflow(project_root=orch_project, resume_run=first.run_id)
    run_json = json.loads((runs[0].parent / "run.json").read_text())
    assert run_json["run_id"] == first.run_id and run_json["paused_at"] is None


def test_checkpoint_confirm_sees_each_gate(orch_project):
    asked = []
    result = run_workflow(_three(), project_root=orch_project, confirm=lambda step, res: asked.append(step.id) or True)
    assert result.ok and asked == ["two", "three"]  # the first step needs no approval: starting the run is it


def test_checkpoint_dry_run_never_pauses(orch_project):
    assert run_workflow(_three(), project_root=orch_project, dry_run=True).ok


# ---------------------------------------------------------------- CLI


def _cli_project(orch_project: Path) -> Path:
    wf_dir = orch_project / ".ai" / "orchestration" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "gated.workflow.json").write_text(
        json.dumps(
            {
                "name": "gated",
                "mode": "checkpoint",
                "steps": [{"id": "one", "command": "echo 1"}, {"id": "two", "command": "echo 2"}],
            }
        )
    )
    return orch_project


def test_cli_checkpoint_pause_resume_and_yes(orch_project):
    project = _cli_project(orch_project)
    runner = CliRunner()
    pr = ["--project-root", str(project)]
    r = runner.invoke(cli, ["orchestrate", "run", "gated", "--json", *pr])
    assert r.exit_code == 3, r.output
    run_id = json.loads(r.output)["run_id"]
    r = runner.invoke(cli, ["orchestrate", "run", "--resume", run_id, *pr])
    assert r.exit_code == 0, r.output
    assert "OK" in r.output
    r = runner.invoke(cli, ["orchestrate", "run", "gated", "--yes", *pr])
    assert r.exit_code == 0, r.output
    r = runner.invoke(cli, ["orchestrate", "run", *pr])
    assert r.exit_code != 0 and "either WORKFLOW or --resume" in r.output


def test_cli_dag_mode(orch_project):
    project = _cli_project(orch_project)
    r = CliRunner().invoke(cli, ["orchestrate", "run", "gated", "--mode", "dag", "--project-root", str(project)])
    assert r.exit_code == 0, r.output
    assert "mode=dag" in r.output
