"""Claude access for the completeness oracle: subscription first, API key optional.

Exercises .ai/scripts/skill-completeness-check.py with a fake `claude` executable,
so no network, no real login and no API key are needed.
"""
# <!-- version: 1.0.0 -->
import importlib.util
import json
import os
import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".ai" / "scripts" / "skill-completeness-check.py"

FAKE_CLAUDE = r'''#!{python}
import json, os, sys
log = os.environ.get("FAKE_CLAUDE_LOG")
args = sys.argv[1:]
if args[:2] == ["auth", "status"]:
    print(json.dumps({{"loggedIn": {logged_in}, "authMethod": "{auth_method}", "subscriptionType": {sub}}}))
    sys.exit(0)
prompt = sys.stdin.read()
if log:
    with open(log, "w") as fh:
        json.dump({{"args": args, "prompt": prompt, "has_api_key": "ANTHROPIC_API_KEY" in os.environ,
                   "cwd": os.getcwd()}}, fh)
mode = os.environ.get("FAKE_CLAUDE_MODE", "ok")
if mode == "error":
    print(json.dumps({{"type": "result", "subtype": "error_during_execution", "is_error": True,
                      "result": "usage limit reached"}}))
    sys.exit(1)
if mode == "garbage":
    print("not json", file=sys.stderr)
    sys.exit(1)
print(json.dumps({{"type": "result", "subtype": "success", "is_error": False,
                  "result": "```json\n{{\"atoms\": [{{\"id\": \"a\", \"type\": \"command\", \"description\": \"d\"}}]}}\n```"}}))
'''


def _load_oracle():
    spec = importlib.util.spec_from_file_location("_oracle_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture()
def oracle():
    return _load_oracle()


def _fake_claude(tmp_path: Path, *, logged_in=True, auth_method="claude.ai", sub='"pro"') -> Path:
    path = tmp_path / "claude"
    path.write_text(FAKE_CLAUDE.format(python=sys.executable, logged_in=logged_in,
                                       auth_method=auth_method, sub=sub))
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _env(**extra):
    base = {k: v for k, v in os.environ.items()
            if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN",
                         "AGENTFACTORY_CLAUDE_BACKEND", "AGENTFACTORY_CLAUDE_BIN")}
    base.update(extra)
    return base


class TestResolveBackend:
    def test_subscription_preferred_over_api_key(self, oracle, tmp_path):
        fake = _fake_claude(tmp_path)
        with patch.dict(os.environ, _env(AGENTFACTORY_CLAUDE_BIN=str(fake), ANTHROPIC_API_KEY="sk-test"), clear=True):
            assert oracle.resolve_backend() == "subscription"

    def test_falls_back_to_api_key_without_login(self, oracle, tmp_path):
        fake = _fake_claude(tmp_path, logged_in=False, sub="None")
        env = _env(AGENTFACTORY_CLAUDE_BIN=str(fake), ANTHROPIC_API_KEY="sk-test")
        with patch.dict(os.environ, env, clear=True), patch.object(oracle, "api_available", return_value=True):
            assert oracle.resolve_backend() == "api"

    def test_console_login_is_not_a_subscription(self, oracle, tmp_path):
        fake = _fake_claude(tmp_path, auth_method="console", sub="None")
        with patch.dict(os.environ, _env(AGENTFACTORY_CLAUDE_BIN=str(fake)), clear=True):
            assert oracle.subscription_available() is False

    def test_oauth_token_env_counts_as_subscription(self, oracle, tmp_path):
        fake = _fake_claude(tmp_path, logged_in=False, sub="None")
        with patch.dict(os.environ, _env(AGENTFACTORY_CLAUDE_BIN=str(fake), CLAUDE_CODE_OAUTH_TOKEN="sk-ant-oat01-x"), clear=True):
            assert oracle.resolve_backend() == "subscription"

    def test_missing_cli_and_key_gives_setup_help(self, oracle, tmp_path):
        with patch.dict(os.environ, _env(AGENTFACTORY_CLAUDE_BIN=str(tmp_path / "nope")), clear=True):
            assert oracle.resolve_backend() is None
            with pytest.raises(oracle.ClaudeAccessError, match="claude auth login"):
                oracle.make_client()

    def test_forced_api_ignores_subscription(self, oracle, tmp_path):
        fake = _fake_claude(tmp_path)
        with patch.dict(os.environ, _env(AGENTFACTORY_CLAUDE_BIN=str(fake), AGENTFACTORY_CLAUDE_BACKEND="api"), clear=True):
            assert oracle.resolve_backend() is None
            with pytest.raises(oracle.ClaudeAccessError, match="ANTHROPIC_API_KEY"):
                oracle.make_client()

    def test_unknown_backend_rejected(self, oracle):
        with pytest.raises(oracle.ClaudeAccessError, match="Unknown Claude backend"):
            oracle.resolve_backend("bedrock")


class TestSubscriptionClient:
    def test_runs_claude_print_without_api_key_and_parses_atoms(self, oracle, tmp_path):
        fake = _fake_claude(tmp_path)
        log = tmp_path / "call.json"
        env = _env(AGENTFACTORY_CLAUDE_BIN=str(fake), ANTHROPIC_API_KEY="sk-should-not-leak",
                   FAKE_CLAUDE_LOG=str(log))
        with patch.dict(os.environ, env, clear=True):
            client = oracle.make_client()
            assert client.backend == "subscription"
            atoms = oracle.phase1_extract_atoms(client, "# Skill\nRun `gh pr list`.", "haiku")
        assert atoms == [{"id": "a", "type": "command", "description": "d"}]
        call = json.loads(log.read_text())
        assert call["has_api_key"] is False
        args = call["args"]
        assert args[:1] == ["-p"] and "--bare" not in args
        assert args[args.index("--model") + 1] == "haiku"
        assert args[args.index("--tools") + 1] == ""
        assert "--no-session-persistence" in args
        assert "Run `gh pr list`." in call["prompt"]
        assert Path(call["cwd"]).name.startswith("af-oracle-")

    @pytest.mark.parametrize("mode,match", [("error", "usage limit reached"), ("garbage", "not json")])
    def test_cli_failures_raise_access_error(self, oracle, tmp_path, mode, match):
        fake = _fake_claude(tmp_path)
        with patch.dict(os.environ, _env(FAKE_CLAUDE_MODE=mode), clear=True):
            client = oracle.SubscriptionClient(claude_bin=str(fake))
            with pytest.raises(oracle.ClaudeAccessError, match=match):
                client.complete(system="s", content="c", model="haiku", max_tokens=10)


def test_api_aliases_map_to_claude_5_family(oracle):
    assert oracle.MODEL_ALIASES == {
        "haiku": "claude-haiku-5-5",
        "sonnet": "claude-sonnet-5-5",
        "opus": "claude-opus-5-5",
    }
    assert oracle._DEFAULT_MODEL == "haiku"


def test_preamble_oracle_returns_none_without_access(tmp_path):
    from agent_gen.librarian import HARNESS_ROOT, _run_preamble_oracle

    scripts = tmp_path / HARNESS_ROOT / "scripts"
    scripts.mkdir(parents=True)
    (scripts / SCRIPT.name).write_text(SCRIPT.read_text())
    with patch.dict(os.environ, _env(AGENTFACTORY_CLAUDE_BIN=str(tmp_path / "nope")), clear=True):
        assert _run_preamble_oracle("a" * 100, "a" * 10, str(tmp_path)) is None
