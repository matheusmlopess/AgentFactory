"""Sequential executor tests: remediation policies, expects, evidence, dry-run.

All runs go through the public API (run_workflow) against a project whose
contract wires agents to the fake stub — the same path the CLI takes.
"""
import json

import pytest

from agent_gen.orchestrate import run_workflow
from agent_gen.orchestrate.executors import EXIT_POLICY_BLOCKED
from agent_gen.orchestrate.models import Workflow, WorkflowStep


def _wf(*steps, name="t", mode="sequential"):
    return Workflow(name=name, mode=mode, steps=list(steps))


def _shell(id, command, **kw):
    return WorkflowStep(id=id, type="shell", command=command, **kw)


def _agent(id, prompt, **kw):
    return WorkflowStep(id=id, type="agent", prompt=prompt, **kw)


class TestHappyPath:
    def test_shell_then_agent_with_templating(self, orch_project):
        wf = _wf(
            _shell("collect", "echo repo-is-clean"),
            _agent("summarize", "Summarize: {steps.collect.stdout}",
                   depends_on=["collect"], expects="nonempty"),
        )
        result = run_workflow(wf, project_root=orch_project)
        assert result.ok, result.statuses
        summarize_ev = [e for e in result.evidence if e.step_id == "summarize"][-1]
        # The stub echoes its prompt back — proves templating rendered stdout in
        assert "repo-is-clean" in summarize_ev.stdout

    def test_dry_run_all_success_no_evidence_dir(self, orch_project):
        wf = _wf(_shell("a", "exit 1"), _agent("b", "MODE:FAIL"))
        result = run_workflow(wf, project_root=orch_project, dry_run=True)
        assert result.ok
        assert not (orch_project / ".ai" / "memory" / "orchestration-runs").exists()


class TestRemediationPolicies:
    def test_retry_recovers_on_second_attempt(self, orch_project, tmp_path):
        flag = tmp_path / "flag"
        cmd = f"test -f {flag} && echo recovered || (touch {flag}; exit 1)"
        wf = _wf(_shell("flaky", cmd, remediation="retry", max_retries=2))
        result = run_workflow(wf, project_root=orch_project)
        assert result.ok
        attempts = [e.attempt for e in result.evidence if e.step_id == "flaky"]
        assert attempts == [1, 2]

    def test_skip_continues_past_failure(self, orch_project):
        wf = _wf(
            _shell("bad", "exit 1", remediation="skip"),
            _shell("after", "echo still-here"),
        )
        result = run_workflow(wf, project_root=orch_project)
        assert result.statuses["bad"] == "skipped"
        assert result.statuses["after"] == "success"
        assert result.ok  # skipped counts as non-blocking

    def test_abort_stops_and_blocks_remaining(self, orch_project):
        wf = _wf(
            _shell("bad", "exit 1", remediation="abort"),
            _shell("never", "echo nope"),
        )
        result = run_workflow(wf, project_root=orch_project)
        assert result.statuses["bad"] == "failed"
        assert result.statuses["never"] == "blocked"
        assert not result.ok

    def test_escalate_fails_cleanly_until_delegate_lands(self, orch_project):
        """PR1: escalate requires the delegate planner (PR3) — run fails, doesn't crash."""
        wf = _wf(
            _shell("bad", "exit 1", remediation="escalate"),
            _shell("never", "echo nope"),
        )
        result = run_workflow(wf, project_root=orch_project)
        assert result.statuses["bad"] == "failed"
        assert result.statuses["never"] == "blocked"

    def test_retry_exhausted_escalates_then_fails(self, orch_project):
        wf = _wf(_shell("bad", "exit 1", remediation="retry", max_retries=2))
        result = run_workflow(wf, project_root=orch_project)
        assert result.statuses["bad"] == "failed"
        attempts = [e.attempt for e in result.evidence if e.step_id == "bad"]
        assert attempts == [1, 2]


class TestExpectsAndPolicies:
    def test_expects_json_violation_fails_step(self, orch_project):
        # Stub replies "ANSWER: …" — not JSON
        wf = _wf(_agent("a", "say something", expects="json", remediation="skip"))
        result = run_workflow(wf, project_root=orch_project)
        assert result.statuses["a"] == "skipped"
        ev = result.evidence[-1]
        assert "expects='json'" in ev.stderr

    def test_expects_json_satisfied(self, orch_project):
        wf = _wf(_agent("a", "MODE:JSON", expects="json"))
        result = run_workflow(wf, project_root=orch_project)
        assert result.ok

    def test_agent_empty_output_fails_step(self, orch_project):
        wf = _wf(_agent("a", "MODE:EMPTY", remediation="abort"))
        result = run_workflow(wf, project_root=orch_project)
        assert result.statuses["a"] == "failed"

    def test_provider_error_fails_step(self, orch_project):
        wf = _wf(_agent("a", "MODE:QUOTA", remediation="abort"))
        result = run_workflow(wf, project_root=orch_project)
        assert result.statuses["a"] == "failed"

    def test_blocked_clearance_refused(self, orch_project):
        wf = _wf(_shell("a", "echo hi", security_clearance="blocked",
                        remediation="abort"))
        result = run_workflow(wf, project_root=orch_project)
        ev = result.evidence[-1]
        assert ev.exit_code == EXIT_POLICY_BLOCKED
        assert "security_clearance" in ev.stderr

    def test_allow_shell_steps_false_refuses_shell(self, orch_project):
        contract_path = orch_project / ".ai" / "config" / "orchestration.json"
        data = json.loads(contract_path.read_text())
        data.setdefault("policies", {})["allow_shell_steps"] = False
        contract_path.write_text(json.dumps(data))

        wf = _wf(_shell("a", "echo hi", remediation="abort"))
        result = run_workflow(wf, project_root=orch_project)
        assert result.evidence[-1].exit_code == EXIT_POLICY_BLOCKED

    def test_unknown_agent_raises(self, orch_project):
        wf = _wf(_agent("a", "hi", agent="ghost"))
        with pytest.raises(ValueError, match="unknown agent 'ghost'"):
            run_workflow(wf, project_root=orch_project)


class TestEvidencePersistence:
    def test_run_json_and_step_files_written(self, orch_project):
        wf = _wf(_shell("a", "echo persisted"))
        result = run_workflow(wf, project_root=orch_project)
        runs_dir = orch_project / ".ai" / "memory" / "orchestration-runs"
        run_dirs = list(runs_dir.iterdir())
        assert len(run_dirs) == 1
        run_data = json.loads((run_dirs[0] / "run.json").read_text())
        assert run_data["ok"] is True
        assert run_data["run_id"] == result.run_id
        stdout_file = run_dirs[0] / "steps" / "a-1.stdout"
        assert stdout_file.read_text().strip() == "persisted"


class TestModeSelection:
    def test_unknown_mode_raises(self, orch_project):
        wf = _wf(_shell("a", "echo hi"), mode="warp")
        with pytest.raises(ValueError, match="unknown execution mode 'warp'"):
            run_workflow(wf, project_root=orch_project)

    def test_mode_override_wins(self, orch_project):
        wf = _wf(_shell("a", "echo hi"), mode="warp")
        result = run_workflow(wf, project_root=orch_project, mode="sequential")
        assert result.ok and result.mode == "sequential"

    def test_register_custom_executor(self, orch_project):
        from agent_gen.orchestrate import register_executor
        from agent_gen.orchestrate.executors import SequentialExecutor, _EXECUTOR_REGISTRY

        class EchoExecutor(SequentialExecutor):
            pass

        register_executor("echo-mode", EchoExecutor)
        try:
            wf = _wf(_shell("a", "echo hi"))
            result = run_workflow(wf, project_root=orch_project, mode="echo-mode")
            assert result.ok
        finally:
            _EXECUTOR_REGISTRY.pop("echo-mode", None)
