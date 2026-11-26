"""#196: delegate steps, escalate re-planning and nested harness runs."""

import json
import sys
from pathlib import Path

import pytest

from agent_gen.orchestrate import Workflow, run_workflow
from agent_gen.orchestrate.delegate import DelegateError, parse_plan
from agent_gen.orchestrate.models import WorkflowStep

# A scripted supervisor: reply N is replies/<N>.txt (the last one repeats). Each call is logged.
_PLANNER_SRC = """\
import pathlib, sys
here = pathlib.Path(sys.argv[1])
log = here / "calls.log"
n = len(log.read_text().splitlines()) + 1 if log.exists() else 1
with log.open("a") as fh:
    fh.write(sys.argv[2].replace("\\n", " ")[-400:] + "\\n")  # the task and any rejection note come last
replies = sorted((here / "replies").glob("*.txt"))
print(replies[min(n, len(replies)) - 1].read_text())
"""


@pytest.fixture
def supervised(orch_project, tmp_path):
    """orch_project whose supervisor (claude) answers with canned replies; returns (project, set_replies, calls)."""
    home = tmp_path / "planner"
    (home / "replies").mkdir(parents=True)
    script = home / "planner.py"
    script.write_text(_PLANNER_SRC)
    cfg_path = orch_project / ".ai" / "config" / "orchestration.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["agents"]["claude"] = {"invocation": [sys.executable, str(script), str(home), "{prompt}"]}
    cfg_path.write_text(json.dumps(cfg))

    def set_replies(*replies, **policies):
        for old in (home / "replies").glob("*.txt"):
            old.unlink()
        (home / "calls.log").unlink(missing_ok=True)  # reply numbering restarts with each script
        for i, reply in enumerate(replies, start=1):
            text = reply if isinstance(reply, str) else json.dumps(reply)
            (home / "replies" / f"{i:02d}.txt").write_text(text)
        if policies:
            data = json.loads(cfg_path.read_text())
            data["policies"].update(policies)
            cfg_path.write_text(json.dumps(data))

    def calls() -> list[str]:
        log = home / "calls.log"
        return log.read_text().splitlines() if log.exists() else []

    return orch_project, set_replies, calls


def _wf(*steps, mode="sequential"):
    return Workflow(name="d", mode=mode, steps=list(steps))


def _delegate(id="plan", prompt="Write release notes", **kw):
    return WorkflowStep(id=id, type="delegate", prompt=prompt, **kw)


AGENT_PLAN = [
    {"id": "draft", "type": "agent", "agent": "fake", "prompt": "draft notes"},
    {"id": "Polish It!", "type": "agent", "agent": "fake", "prompt": "polish", "depends_on": ["draft"]},
]


# ---------------------------------------------------------------- parsing


@pytest.mark.parametrize(
    "raw",
    [
        '[{"id": "a", "command": "true"}]',
        'Here is the plan:\n```json\n[{"id": "a", "command": "true"}]\n```\nDone.',
        'Sure. [{"id": "a", "command": "true"}]',
        '{"steps": [{"id": "a", "command": "true"}]}',
    ],
)
def test_parse_plan_accepts_common_reply_shapes(raw):
    assert parse_plan(raw) == [{"id": "a", "command": "true"}]


@pytest.mark.parametrize("raw", ["no json here", "[1, 2]", '{"answer": 1}', "[{broken"])
def test_parse_plan_rejects_non_plans(raw):
    with pytest.raises(DelegateError):
        parse_plan(raw)


# ---------------------------------------------------------------- delegate steps


def test_delegate_plans_splices_and_runs_substeps(supervised):
    project, set_replies, calls = supervised
    set_replies(AGENT_PLAN)
    result = run_workflow(_wf(_delegate(), WorkflowStep(id="after", command="echo done")), project_root=project)
    assert result.ok, result.statuses
    assert list(result.statuses) == ["plan", "plan-draft", "plan-polish-it", "after"]
    snapshot = {s["id"]: s for s in result.workflow_snapshot["steps"]}
    assert snapshot["plan-polish-it"]["depends_on"] == ["plan-draft"]  # ids rewritten consistently
    assert result.evidence[0].step_id == "plan.plan"  # the supervisor call is evidence too
    assert len(calls()) == 1 and "Write release notes" in calls()[0]


def test_bad_reply_gets_one_reprompt(supervised):
    project, set_replies, calls = supervised
    set_replies("I would rather chat.", AGENT_PLAN)
    result = run_workflow(_wf(_delegate()), project_root=project)
    assert result.ok and len(calls()) == 2
    assert "previous reply was rejected" in calls()[1]


def test_bad_replies_fail_the_step_or_skip_it(supervised):
    project, set_replies, _ = supervised
    set_replies("nope")
    failed = run_workflow(_wf(_delegate(), WorkflowStep(id="after", command="echo x")), project_root=project)
    assert failed.statuses == {"plan": "failed", "after": "blocked"}
    skipped = run_workflow(_wf(_delegate(remediation="skip"), WorkflowStep(id="after", command="echo x")),
                           project_root=project)  # fmt: skip
    assert skipped.statuses == {"plan": "skipped", "after": "success"}


def test_planned_shell_steps_need_an_explicit_opt_in(supervised, tmp_path):
    project, set_replies, _ = supervised
    marker = tmp_path / "ran"
    set_replies([{"id": "sh", "type": "shell", "command": f"touch {marker}"}])
    assert run_workflow(_wf(_delegate()), project_root=project).statuses["plan"] == "failed"
    assert not marker.exists()
    set_replies([{"id": "sh", "type": "shell", "command": f"touch {marker}"}], delegate_shell_steps=True)
    assert run_workflow(_wf(_delegate()), project_root=project).ok
    assert marker.exists()


def test_plan_size_and_nesting_limits(supervised):
    project, set_replies, _ = supervised
    set_replies([{"id": f"s{i}", "agent": "fake", "prompt": "x"} for i in range(3)], max_delegate_steps=2)
    assert run_workflow(_wf(_delegate()), project_root=project).statuses["plan"] == "failed"

    nested = [{"id": "inner", "type": "delegate", "prompt": "plan more"}]
    set_replies(nested, max_delegate_steps=12)  # default max_delegate_depth=1: no delegate inside a delegate
    assert run_workflow(_wf(_delegate()), project_root=project).statuses["plan"] == "failed"

    set_replies(nested, [{"id": "leaf", "agent": "fake", "prompt": "x"}], max_delegate_depth=2)
    result = run_workflow(_wf(_delegate()), project_root=project)
    assert result.ok and "plan-inner-leaf" in result.statuses


def test_dry_run_does_not_call_the_supervisor(supervised):
    project, set_replies, calls = supervised
    set_replies(AGENT_PLAN)
    assert run_workflow(_wf(_delegate()), project_root=project, dry_run=True).ok
    assert calls() == []


def test_disabled_supervisor_fails_the_step(supervised):
    project, _, calls = supervised
    cfg_path = project / ".ai" / "config" / "orchestration.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["agents"]["claude"]["enabled"] = False
    cfg_path.write_text(json.dumps(cfg))
    assert run_workflow(_wf(_delegate()), project_root=project).statuses["plan"] == "failed"
    assert calls() == []


# ---------------------------------------------------------------- escalate


def test_escalate_replaces_the_failed_step_with_a_plan(supervised):
    project, set_replies, calls = supervised
    set_replies([{"id": "fixed", "agent": "fake", "prompt": "do it another way"}])
    wf = _wf(
        WorkflowStep(id="build", command="exit 4", remediation="escalate"), WorkflowStep(id="ship", command="true")
    )
    result = run_workflow(wf, project_root=project)
    assert result.ok, result.statuses
    assert "build" not in result.statuses and result.statuses["build-fixed"] == "success"
    assert "Exit code: 4" in calls()[0]


def test_escalate_stops_after_max_remediation_rounds(supervised):
    project, set_replies, calls = supervised
    set_replies([{"id": "again", "agent": "fake", "prompt": "MODE:FAIL", "remediation": "escalate"}],
                max_remediation_rounds=2)  # fmt: skip
    result = run_workflow(_wf(WorkflowStep(id="build", command="exit 1", remediation="escalate")), project_root=project)
    assert not result.ok and len(calls()) == 2


def test_checkpoint_resume_keeps_planned_steps(supervised):
    project, set_replies, calls = supervised
    set_replies(AGENT_PLAN)
    first = run_workflow(_wf(_delegate(), mode="checkpoint"), project_root=project)
    assert first.paused_at == "plan-draft"
    done = run_workflow(project_root=project, resume_run=first.run_id, confirm=lambda s, r: True)
    assert done.ok and len(calls()) == 1  # resuming does not re-plan


# ---------------------------------------------------------------- nested harness


def _harness_project(orch_project: Path, *, max_depth: int) -> Path:
    cfg_path = orch_project / ".ai" / "config" / "orchestration.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["agents"]["harness"] = {
        "invocation": [sys.executable, "-m", "agent_gen", "orchestrate", "run", "{workflow}", "--json"]
    }
    cfg["policies"]["max_delegate_depth"] = max_depth
    cfg_path.write_text(json.dumps(cfg))
    wf_dir = orch_project / ".ai" / "orchestration" / "workflows"
    wf_dir.mkdir(parents=True)
    leaf = {"name": "leaf", "steps": [{"id": "hello", "command": "echo from-leaf"}]}
    middle = {"name": "middle", "steps": [{"id": "call-leaf", "type": "agent", "agent": "harness", "prompt": "leaf"}]}
    (wf_dir / "leaf.workflow.json").write_text(json.dumps(leaf))
    (wf_dir / "middle.workflow.json").write_text(json.dumps(middle))
    return orch_project


def _harness_step(target):
    return WorkflowStep(id="nested", type="agent", agent="harness", prompt=target, expects="json")


def test_harness_step_runs_a_child_workflow(orch_project):
    project = _harness_project(orch_project, max_depth=1)
    result = run_workflow(_wf(_harness_step("leaf")), project_root=project)
    assert result.ok, [e.stderr for e in result.evidence]
    child = json.loads(result.evidence[-1].stdout)
    assert child["workflow_name"] == "leaf" and child["statuses"] == {"hello": "success"}


def test_nesting_past_max_delegate_depth_is_refused(orch_project):
    project = _harness_project(orch_project, max_depth=1)
    result = run_workflow(_wf(_harness_step("middle")), project_root=project)  # depth 0 → 1 → 2
    assert not result.ok
    assert "exceeds max_delegate_depth" in result.evidence[-1].stdout + result.evidence[-1].stderr
    cfg_path = project / ".ai" / "config" / "orchestration.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["policies"]["max_delegate_depth"] = 2
    cfg_path.write_text(json.dumps(cfg))
    assert run_workflow(_wf(_harness_step("middle")), project_root=project).ok  # depth 2 allowed now
