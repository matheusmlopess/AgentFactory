"""CLI tests for the `agentfactory-gen orchestrate` command group."""
import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_gen.cli import cli
from conftest import make_contract


@pytest.fixture
def runner():
    return CliRunner()


def _init_project(runner, fake_agent_script=None):
    """init a project in CWD; optionally wire the contract to the fake agent."""
    r = runner.invoke(cli, ["--quiet", "init"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(cli, ["--quiet", "orchestrate", "init"])
    assert r.exit_code == 0, r.output
    if fake_agent_script is not None:
        contract_path = Path(".ai/config/orchestration.json")
        data = json.loads(contract_path.read_text())
        for name, spec in make_contract(fake_agent_script)["agents"].items():
            data["agents"][name] = spec
        contract_path.write_text(json.dumps(data))


class TestOrchestrateInit:
    def test_scaffolds_contract_and_example(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["--quiet", "init"])
            r = runner.invoke(cli, ["orchestrate", "init"])
            assert r.exit_code == 0, r.output
            assert Path(".ai/config/orchestration.json").exists()
            assert Path(".ai/orchestration/workflows/example.workflow.json").exists()

    def test_idempotent_never_clobbers(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["--quiet", "init"])
            runner.invoke(cli, ["orchestrate", "init"])
            contract_path = Path(".ai/config/orchestration.json")
            contract_path.write_text('{"default_mode": "sequential"}')
            r = runner.invoke(cli, ["orchestrate", "init"])
            assert r.exit_code == 0
            assert "skip" in r.output
            assert json.loads(contract_path.read_text()) == {"default_mode": "sequential"}

    def test_requires_harness(self, runner):
        with runner.isolated_filesystem():
            r = runner.invoke(cli, ["orchestrate", "init"])
            assert r.exit_code != 0
            assert "not an AgentFactory project" in r.output


class TestOrchestrateValidate:
    def test_example_workflow_valid(self, runner):
        with runner.isolated_filesystem():
            _init_project(runner)
            r = runner.invoke(cli, ["orchestrate", "validate", "example"])
            assert r.exit_code == 0, r.output
            assert "valid" in r.output

    def test_invalid_workflow_exits_one(self, runner):
        with runner.isolated_filesystem():
            _init_project(runner)
            bad = Path(".ai/orchestration/workflows/bad.workflow.json")
            bad.write_text(json.dumps({"name": "bad", "steps": [{"id": "a"}]}))
            r = runner.invoke(cli, ["orchestrate", "validate", "bad"])
            assert r.exit_code == 1
            assert "requires 'command'" in r.output

    def test_unknown_step_agent_reported(self, runner):
        with runner.isolated_filesystem():
            _init_project(runner)
            wf = Path(".ai/orchestration/workflows/ghost.workflow.json")
            wf.write_text(json.dumps({
                "name": "ghost",
                "steps": [{"id": "a", "type": "agent", "agent": "ghost", "prompt": "x"}],
            }))
            r = runner.invoke(cli, ["orchestrate", "validate", "ghost"])
            assert r.exit_code == 1
            assert "unknown agent 'ghost'" in r.output


class TestOrchestrateList:
    def test_empty_hint(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["--quiet", "init"])
            r = runner.invoke(cli, ["orchestrate", "list"])
            assert r.exit_code == 0
            assert "no workflows found" in r.output

    def test_lists_project_and_agent_workflows(self, runner):
        with runner.isolated_filesystem():
            _init_project(runner)
            runner.invoke(cli, ["--quiet", "deploy", "wf-agent"])
            agent_wf = Path(".ai/agents/wf-agent/orchestration/workflows")
            agent_wf.mkdir(parents=True)
            (agent_wf / "deploy.workflow.json").write_text(
                json.dumps({"name": "deploy", "steps": []})
            )
            r = runner.invoke(cli, ["orchestrate", "list"])
            assert "example" in r.output
            assert "wf-agent/deploy" in r.output


class TestOrchestrateRun:
    def test_dry_run_example(self, runner):
        with runner.isolated_filesystem():
            _init_project(runner)
            r = runner.invoke(cli, ["orchestrate", "run", "example", "--dry-run"])
            assert r.exit_code == 0, r.output
            assert "OK" in r.output

    def test_run_with_fake_agent_writes_evidence(self, runner, fake_agent_script):
        with runner.isolated_filesystem():
            _init_project(runner, fake_agent_script)
            r = runner.invoke(cli, ["orchestrate", "run", "example"])
            assert r.exit_code == 0, r.output
            runs = list(Path(".ai/memory/orchestration-runs").iterdir())
            assert len(runs) == 1
            assert (runs[0] / "run.json").exists()

    def test_run_json_output_is_machine_readable(self, runner, fake_agent_script):
        with runner.isolated_filesystem():
            _init_project(runner, fake_agent_script)
            r = runner.invoke(cli, ["orchestrate", "run", "example", "--json"])
            assert r.exit_code == 0, r.output
            data = json.loads(r.output)
            assert data["ok"] is True
            assert data["statuses"]["collect"] == "success"

    def test_failing_workflow_exits_one(self, runner, fake_agent_script):
        with runner.isolated_filesystem():
            _init_project(runner, fake_agent_script)
            wf = Path(".ai/orchestration/workflows/fail.workflow.json")
            wf.write_text(json.dumps({
                "name": "fail",
                "steps": [{"id": "a", "command": "exit 1", "remediation": "abort"}],
            }))
            r = runner.invoke(cli, ["orchestrate", "run", "fail"])
            assert r.exit_code == 1
            assert "FAILED" in r.output

    def test_agent_shorthand_resolution(self, runner, fake_agent_script):
        with runner.isolated_filesystem():
            _init_project(runner, fake_agent_script)
            runner.invoke(cli, ["--quiet", "deploy", "wf-agent"])
            agent_wf = Path(".ai/agents/wf-agent/orchestration/workflows")
            agent_wf.mkdir(parents=True)
            (agent_wf / "hello.workflow.json").write_text(json.dumps({
                "name": "hello",
                "steps": [{"id": "a", "command": "echo hi"}],
            }))
            r = runner.invoke(cli, ["orchestrate", "run", "wf-agent/hello"])
            assert r.exit_code == 0, r.output

    def test_unknown_workflow_clear_error(self, runner):
        with runner.isolated_filesystem():
            _init_project(runner)
            r = runner.invoke(cli, ["orchestrate", "run", "ghost"])
            assert r.exit_code != 0
            assert "not found" in r.output

    def test_mode_override_flag(self, runner, fake_agent_script):
        with runner.isolated_filesystem():
            _init_project(runner, fake_agent_script)
            r = runner.invoke(
                cli, ["orchestrate", "run", "example", "--mode", "warp"]
            )
            assert r.exit_code != 0
            assert "unknown execution mode" in r.output


class TestNestedDepthGuard:
    def test_depth_over_limit_refused(self, runner, fake_agent_script):
        with runner.isolated_filesystem():
            _init_project(runner, fake_agent_script)
            old = os.environ.get("AGENTFACTORY_ORCH_DEPTH")
            os.environ["AGENTFACTORY_ORCH_DEPTH"] = "5"
            try:
                r = runner.invoke(cli, ["orchestrate", "run", "example"])
                assert r.exit_code != 0
                assert "depth" in r.output
            finally:
                if old is None:
                    os.environ.pop("AGENTFACTORY_ORCH_DEPTH", None)
                else:
                    os.environ["AGENTFACTORY_ORCH_DEPTH"] = old
