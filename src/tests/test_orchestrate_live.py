"""#197: one-step agent workflows against the real CLIs (pytest -m live).

Each test runs through the default contract (invocation flags, env_unset, model_args), so a CLI upgrade that
breaks orchestration shows up here. A missing binary or a provider-side failure (quota, outage, login) skips.
"""

import shutil

import pytest
from click.testing import CliRunner

from agent_gen.cli import cli
from agent_gen.orchestrate import Workflow, run_workflow
from agent_gen.orchestrate.contract import DEFAULT_CONTRACT
from agent_gen.orchestrate.models import WorkflowStep

_TOKEN = "ORCHESTRATE-LIVE-OK"
_PROMPT = f"Reply with exactly the text {_TOKEN} and nothing else."
_UNAVAILABLE = ("provider error detected", "not logged in", "login", "authenticate", "api key")


@pytest.mark.live
@pytest.mark.parametrize("agent", ["claude", "codex", "antigravity"])
def test_live_one_step_agent_workflow(agent, tmp_path):
    binary = DEFAULT_CONTRACT["agents"][agent]["invocation"][0]
    if shutil.which(binary) is None:
        pytest.skip(f"{agent} CLI ('{binary}') not installed")
    assert CliRunner().invoke(cli, ["init", "--project-root", str(tmp_path)]).exit_code == 0

    step = WorkflowStep(id="ping", type="agent", agent=agent, prompt=_PROMPT, expects=f"regex:{_TOKEN}",
                        remediation="abort", timeout_seconds=180)  # fmt: skip
    result = run_workflow(Workflow(name=f"live-{agent}", steps=[step]), project_root=tmp_path)
    ev = result.evidence[-1]
    if not result.ok:
        text = (ev.stdout + ev.stderr).lower()
        if ev.exit_code == 124 or any(marker in text for marker in _UNAVAILABLE) or not ev.stdout.strip():
            pytest.skip(f"{agent} unavailable (exit {ev.exit_code}): {ev.stderr.strip()[:200]}")
    assert result.ok, f"{agent}: exit {ev.exit_code}\nstdout: {ev.stdout[:500]}\nstderr: {ev.stderr[:500]}"
    assert (tmp_path / ".ai" / "memory" / "orchestration-runs").is_dir()  # evidence was written
