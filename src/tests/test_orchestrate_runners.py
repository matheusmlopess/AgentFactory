"""Runner tests — real subprocesses via the fake-agent stub (no monkeypatching)."""
import sys

from agent_gen.orchestrate.models import (
    EXIT_EXPECTS_FAILED,
    EXIT_TIMEOUT,
    WorkflowStep,
)
from agent_gen.orchestrate.runners import CliAgentRunner, ShellRunner


def _step(**kw):
    kw.setdefault("id", "s1")
    kw.setdefault("type", "agent")
    kw.setdefault("prompt", "hi")
    return WorkflowStep(**kw)


def _runner(fake_agent_script, spec_extra=None, policies=None, dry_run=False):
    spec = {"invocation": [sys.executable, str(fake_agent_script), "{prompt}"]}
    spec.update(spec_extra or {})
    return CliAgentRunner("fake", spec, policies or {}, dry_run=dry_run)


class TestShellRunner:
    def test_success(self):
        ev = ShellRunner().run(_step(type="shell", command="echo hi"), "echo hi")
        assert ev.succeeded and ev.stdout.strip() == "hi"

    def test_failure_exit_code(self):
        ev = ShellRunner().run(_step(type="shell", command="exit 3"), "exit 3")
        assert ev.exit_code == 3

    def test_timeout_exit_124(self):
        step = _step(type="shell", command="sleep 5", timeout_seconds=1)
        ev = ShellRunner().run(step, "sleep 5")
        assert ev.exit_code == EXIT_TIMEOUT
        assert "timed out" in ev.stderr

    def test_dry_run_never_executes(self, tmp_path):
        marker = tmp_path / "executed"
        cmd = f"touch {marker}"
        ev = ShellRunner(dry_run=True).run(_step(type="shell", command=cmd), cmd)
        assert ev.succeeded
        assert "[dry-run]" in ev.stdout
        assert not marker.exists()


class TestCliAgentRunner:
    def test_prompt_substitution_and_echo(self, fake_agent_script):
        ev = _runner(fake_agent_script).run(_step(), "summarize this")
        assert ev.succeeded
        assert ev.stdout.strip() == "ANSWER: summarize this"

    def test_empty_output_is_failure_by_default(self, fake_agent_script):
        ev = _runner(fake_agent_script).run(_step(), "MODE:EMPTY")
        assert ev.exit_code == EXIT_EXPECTS_FAILED
        assert "empty output" in ev.stderr

    def test_empty_output_allowed_when_disabled(self, fake_agent_script):
        runner = _runner(fake_agent_script, spec_extra={"empty_output_is_failure": False})
        ev = runner.run(_step(), "MODE:EMPTY")
        assert ev.succeeded

    def test_provider_error_marker_detected(self, fake_agent_script):
        ev = _runner(fake_agent_script).run(_step(), "MODE:QUOTA")
        assert ev.exit_code == EXIT_EXPECTS_FAILED
        assert "provider error" in ev.stderr

    def test_nonzero_exit_passes_through(self, fake_agent_script):
        ev = _runner(fake_agent_script).run(_step(), "MODE:FAIL")
        assert ev.exit_code == 3

    def test_missing_binary_exit_127(self):
        runner = CliAgentRunner(
            "ghost", {"invocation": ["definitely-not-a-binary-xyz", "{prompt}"]}, {}
        )
        ev = runner.run(_step(), "hi")
        assert ev.exit_code == 127
        assert "not found" in ev.stderr

    def test_env_unset_strips_api_key_for_subscription(self, fake_agent_script, monkeypatch, tmp_path):
        probe = tmp_path / "probe.py"
        probe.write_text("import os; print('KEY' if 'ANTHROPIC_API_KEY' in os.environ else 'NOKEY')")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.delenv("AGENTFACTORY_CLAUDE_BACKEND", raising=False)
        spec = {"invocation": [sys.executable, str(probe)], "env_unset": ["ANTHROPIC_API_KEY"]}
        ev = CliAgentRunner("claude", spec, {}).run(_step(), "hi")
        assert ev.stdout.strip() == "NOKEY"
        monkeypatch.setenv("AGENTFACTORY_CLAUDE_BACKEND", "api")
        ev = CliAgentRunner("claude", spec, {}).run(_step(), "hi")
        assert ev.stdout.strip() == "KEY"

    def test_default_claude_contract_strips_api_key_vars(self):
        from agent_gen.orchestrate.contract import DEFAULT_CONTRACT

        assert DEFAULT_CONTRACT["agents"]["claude"]["env_unset"] == [
            "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
        ]

    def test_dry_run(self, fake_agent_script):
        ev = _runner(fake_agent_script, dry_run=True).run(_step(), "MODE:FAIL")
        assert ev.succeeded
        assert "[dry-run]" in ev.stdout
