"""Shared fixtures for the orchestration test suite.

The fake agent is a real subprocess (a tiny python script) wired in through
the orchestration contract's per-agent `invocation` override — the designed
test seam. No subprocess monkeypatching anywhere.
"""
import json
import sys
from pathlib import Path

import pytest

# Behavior is keyed by markers inside the prompt itself, so one stub covers
# every scenario: echo (default), empty output, provider error, hard failure.
_FAKE_AGENT_SRC = """\
import sys

prompt = sys.argv[1] if len(sys.argv) > 1 else ""
if "MODE:EMPTY" in prompt:
    sys.exit(0)
if "MODE:QUOTA" in prompt:
    print("usage limit reached, try later")
    sys.exit(0)
if "MODE:FAIL" in prompt:
    print("cannot comply")
    sys.exit(3)
if "MODE:JSON" in prompt:
    print('{"answer": 42}')
    sys.exit(0)
print("ANSWER: " + prompt)
"""


@pytest.fixture
def fake_agent_script(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("stub") / "fake_agent.py"
    path.write_text(_FAKE_AGENT_SRC, encoding="utf-8")
    return path


def make_contract(fake_agent_script: Path) -> dict:
    """Contract overrides pointing every relevant agent at the stub."""
    invocation = [sys.executable, str(fake_agent_script), "{prompt}"]
    return {
        "agents": {
            "claude": {"invocation": invocation},
            "fake": {"invocation": invocation},
        },
        "policies": {"timeout_seconds": 30},
    }


@pytest.fixture
def orch_project(tmp_path, fake_agent_script) -> Path:
    """Minimal project with .ai/ harness + contract wired to the fake agent."""
    proj = tmp_path / "proj"
    config_dir = proj / ".ai" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "orchestration.json").write_text(
        json.dumps(make_contract(fake_agent_script), indent=2), encoding="utf-8"
    )
    return proj
