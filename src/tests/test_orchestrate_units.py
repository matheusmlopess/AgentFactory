"""#197: Portable Units carry workflows — sync, audit, wrap → import (gated) → orchestrate run."""

import json
import zipfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_gen.cli import cli
from agent_gen.core.safety import _inspect_zip, _workflow_has_shell_steps

SHELL_WF = {"name": "hello", "steps": [{"id": "greet", "type": "shell", "command": "echo hello-from-unit"}]}
PLAN = {"version": "craft-plan/0.1", "name": "ask", "steps": [{"id": "ask", "type": "agent", "prompt": "hi"}]}


def _ok(result):
    assert result.exit_code == 0, result.output
    return result


def _unit(project: Path, runner: CliRunner, workflows: dict[str, object]) -> Path:
    pr = ["--project-root", str(project)]
    _ok(runner.invoke(cli, ["init", *pr]))
    _ok(runner.invoke(cli, ["deploy", "porter", *pr]))
    wf_dir = project / ".ai" / "agents" / "porter" / "orchestration" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    for name, body in workflows.items():
        (wf_dir / name).write_text(body if isinstance(body, str) else json.dumps(body))
    return project / ".ai" / "agents" / "porter"


def test_sync_prefers_a_workflow_as_orchestration_plan(tmp_path):
    runner = CliRunner()
    agent = _unit(tmp_path, runner, {"hello.workflow.json": SHELL_WF})
    (agent / "orchestration" / "AGENTS.md").write_text("<!-- version: 1.0.0 -->\n# notes\n")
    _ok(runner.invoke(cli, ["audit", "porter", "--fix", "--project-root", str(tmp_path)]))
    manifest = json.loads((agent / "agent-manifest.json").read_text())
    assert manifest["orchestration_plan"] == "orchestration/workflows/hello.workflow.json"


def test_audit_warns_about_workflows_that_do_not_load(tmp_path):
    runner = CliRunner()
    bad = {"name": "bad", "steps": [{"id": "a", "command": "x", "depends_on": ["ghost"]}]}
    _unit(tmp_path, runner, {"hello.workflow.json": SHELL_WF, "bad.workflow.json": bad, "ask.plan.json": PLAN})
    result = _ok(runner.invoke(cli, ["audit", "porter", "--fix", "--project-root", str(tmp_path)]))
    assert "Workflows that do not load" in result.output
    assert "bad.workflow.json" in result.output and "ghost" in result.output
    assert "hello.workflow.json:" not in result.output and "ask.plan.json:" not in result.output


@pytest.mark.parametrize(
    "name,body,flagged",
    [
        ("w/x.plan.json", json.dumps({**PLAN, "steps": [{"id": "s", "type": "shell", "command": "id"}]}), True),
        ("w/x.plan.json", json.dumps(PLAN), False),
        (
            "orchestration/workflows/x.md",
            '---\nname: x\n---\n```json\n{"steps": [{"id": "a", "command": "id"}]}\n```\n',
            True,
        ),
        ("orchestration/workflows/notes.md", "# just notes\n", False),
    ],
)
def test_shell_step_gate_covers_every_workflow_dialect(name, body, flagged):
    assert _workflow_has_shell_steps(body.encode(), name) is flagged


def test_wrapped_unit_imports_behind_the_gate_and_runs(tmp_path):
    runner = CliRunner()
    src, dst = tmp_path / "src", tmp_path / "dst"
    _unit(src, runner, {"hello.workflow.json": SHELL_WF})
    _ok(runner.invoke(cli, ["audit", "porter", "--fix", "--project-root", str(src)]))
    zip_path = Path(
        _ok(runner.invoke(cli, ["wrap", "porter", "--project-root", str(src), "--out", str(tmp_path), "--print-path"]))
        .output.strip()
        .splitlines()[-1]
    )
    with zipfile.ZipFile(zip_path) as zf:
        assert "orchestration/workflows/hello.workflow.json" in zf.namelist()
    assert "orchestration/workflows/hello.workflow.json" in _inspect_zip(zip_path)["executable_files"]

    dst.mkdir()
    _ok(runner.invoke(cli, ["init", "--project-root", str(dst)]))
    refused = runner.invoke(cli, ["import", str(zip_path), "--project-root", str(dst)], input="n\n")
    assert "hello.workflow.json" in refused.output  # the shell step is shown before anything is installed
    assert not (dst / ".ai" / "agents" / "porter").exists()

    _ok(runner.invoke(cli, ["import", str(zip_path), "--project-root", str(dst), "--allow-scripts"]))
    result = _ok(runner.invoke(cli, ["orchestrate", "run", "porter/hello", "--json", "--project-root", str(dst)]))
    run = json.loads(result.output)
    assert run["statuses"] == {"greet": "success"}
    assert run["evidence"][0]["stdout"].strip() == "hello-from-unit"
