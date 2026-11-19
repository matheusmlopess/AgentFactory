"""#194: canonical craft-plan/0.1 (CRAFT ADR 0002) ⇄ AgentFactory workflows."""

import copy
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_gen.cli import cli
from agent_gen.orchestrate import Workflow, load_workflow, run_workflow, validate_workflow_data
from agent_gen.orchestrate.canonical import FORMAT, canonical_issues, from_canonical, to_canonical
from agent_gen.orchestrate.executors import EXIT_POLICY_BLOCKED
from agent_gen.orchestrate.runners import CliAgentRunner

SAMPLE = {
    "version": FORMAT,
    "name": "release-notes",
    "description": "Collect the changelog and summarize it.",
    "mode": "sequential",
    "x-studio": {"nodes": {"collect": {"x": 40, "y": 80}, "summarize": {"x": 260, "y": 80}}},
    "x-af": {"version": "2.1.0"},
    "steps": [
        {"id": "collect", "type": "shell", "command": "echo changelog", "remediation": "retry", "max_retries": 2},
        {
            "id": "summarize",
            "type": "agent",
            "agent": "agy",
            "provider": "cli",
            "model": "gemini-3-pro",
            "prompt": "Summarize: {steps.collect.stdout}",
            "depends_on": ["collect"],
            "expects": "nonempty",
            "x-studio-color": "teal",
        },
        {"id": "sdk-review", "type": "agent", "provider": "anthropic", "prompt": "Review the summary"},
    ],
}


def test_sample_plan_loads_into_the_internal_model():
    wf = from_canonical(copy.deepcopy(SAMPLE))
    assert (wf.name, wf.version, wf.mode) == ("release-notes", "2.1.0", "sequential")
    collect, summarize, review = wf.steps
    assert (collect.remediation, collect.max_retries) == ("retry", 2)
    assert summarize.agent == "antigravity"  # canonical agy → AgentFactory contract key
    assert summarize.model == "gemini-3-pro" and summarize.provider == "cli"
    assert summarize.extensions == {"x-studio-color": "teal"}
    assert review.provider == "anthropic"
    assert wf.extensions == {"x-studio": SAMPLE["x-studio"]}


def test_round_trip_preserves_the_plan_exactly():
    assert to_canonical(from_canonical(copy.deepcopy(SAMPLE))) == SAMPLE


def test_af_workflow_to_canonical_and_back():
    af = Workflow.from_dict(
        {
            "name": "af-native",
            "version": "1.4.0",
            "steps": [
                {"id": "a", "type": "shell", "command": "true"},
                {"id": "b", "type": "agent", "agent": "claude", "prompt": "hi", "depends_on": ["a"]},
            ],
        }
    )
    plan = to_canonical(af)
    assert plan["version"] == FORMAT and plan["x-af"] == {"version": "1.4.0"}
    assert "seq" not in plan["steps"][0] and "workflow_id" not in plan
    # Fields the af file did not set stay unset, so contract policies still fill them in at run time.
    assert "timeout_seconds" not in plan["steps"][0] and "remediation" not in plan["steps"][1]
    back = from_canonical(plan)
    assert [s.to_dict() | {"seq": 0} for s in back.steps] == [s.to_dict() | {"seq": 0} for s in af.steps]


@pytest.mark.parametrize(
    "mutate,expected",
    [
        (lambda p: p.update(version="1.0.0"), "version must be"),
        (lambda p: p["steps"][0].update(id="Collect Step"), "must match"),
        (lambda p: p["steps"][0].update(kind="shell"), "unknown field"),
        (lambda p: p.update(owner="me"), "unknown root field"),
        (lambda p: p["steps"][2].update(provider="bedrock"), "provider must be one of"),
        (lambda p: p["steps"][0].update(max_retries=-1), "non-negative integer"),
    ],
)
def test_schema_problems_are_reported(mutate, expected):
    plan = copy.deepcopy(SAMPLE)
    mutate(plan)
    assert any(expected in issue for issue in canonical_issues(plan)), canonical_issues(plan)
    with pytest.raises(ValueError):
        from_canonical(plan)


def test_validate_workflow_data_understands_both_dialects():
    assert validate_workflow_data(copy.deepcopy(SAMPLE)) == []
    assert validate_workflow_data({"name": "af", "steps": [{"id": "a", "command": "true"}]}) == []
    bad = copy.deepcopy(SAMPLE)
    bad["steps"][0]["id"] = "UPPER"
    assert validate_workflow_data(bad)


def test_to_canonical_rejects_ids_the_format_does_not_allow():
    wf = Workflow.from_dict({"name": "x", "steps": [{"id": "Build Step", "command": "true"}]})
    with pytest.raises(ValueError, match="must match"):
        to_canonical(wf)


def test_model_is_passed_when_the_contract_declares_model_args():
    spec = {"invocation": ["claude", "--print", "{prompt}"], "model_args": ["--model", "{model}"]}
    runner = CliAgentRunner("claude", spec, {})
    assert runner._build_command("hi", "sonnet") == ["claude", "--print", "--model", "sonnet", "hi"]
    assert runner._build_command("hi") == ["claude", "--print", "hi"]
    plain = CliAgentRunner("agy", {"invocation": ["agy", "-p", "{prompt}"]}, {})
    assert plain._build_command("hi", "x") == ["agy", "-p", "hi"]


def test_executor_refuses_sdk_provider_steps(orch_project):
    plan = {
        "version": FORMAT,
        "name": "sdk",
        "steps": [
            {"id": "ok", "type": "shell", "command": "echo fine"},
            {"id": "sdk", "type": "agent", "provider": "openai", "prompt": "hi", "remediation": "skip"},
        ],
    }
    result = run_workflow(from_canonical(plan), project_root=orch_project)
    ev = {e.step_id: e for e in result.evidence}
    assert ev["ok"].exit_code == 0
    assert ev["sdk"].exit_code == EXIT_POLICY_BLOCKED and "provider 'openai'" in ev["sdk"].stderr
    assert result.statuses["sdk"] == "skipped"


def _project(tmp_path: Path) -> Path:
    runner = CliRunner()
    assert runner.invoke(cli, ["init", "--project-root", str(tmp_path)]).exit_code == 0
    wf_dir = tmp_path / ".ai" / "orchestration" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    plan = copy.deepcopy(SAMPLE)
    plan["steps"] = plan["steps"][:1]  # shell-only: runnable without any CLI agent
    (wf_dir / "notes.plan.json").write_text(json.dumps(plan))
    return tmp_path


def test_cli_validate_list_run_and_convert_a_canonical_plan(tmp_path):
    project = _project(tmp_path)
    runner = CliRunner()
    pr = ["--project-root", str(project)]
    r = runner.invoke(cli, ["orchestrate", "validate", "notes", *pr])
    assert r.exit_code == 0, r.output
    assert f"({FORMAT})" in r.output
    assert "notes" in runner.invoke(cli, ["orchestrate", "list", *pr]).output
    r = runner.invoke(cli, ["orchestrate", "run", "notes", "--dry-run", *pr])
    assert r.exit_code == 0, r.output

    out = tmp_path / "notes.workflow.json"
    r = runner.invoke(cli, ["orchestrate", "convert", "notes", "--to", "af", "-o", str(out), *pr])
    assert r.exit_code == 0, r.output
    af = json.loads(out.read_text())
    assert af["version"] == "2.1.0" and "workflow_id" not in af and "seq" not in af["steps"][0]
    r = runner.invoke(cli, ["orchestrate", "convert", str(out), "--to", "canonical", *pr])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["version"] == FORMAT


def test_load_workflow_reads_a_plan_file(tmp_path):
    p = tmp_path / "x.plan.json"
    p.write_text(json.dumps(SAMPLE))
    assert load_workflow(p).name == "release-notes"
