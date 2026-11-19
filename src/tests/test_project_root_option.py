"""#190: every command that touches .ai/ takes --project-root and works from any directory."""

import json
import os
from pathlib import Path

from click.testing import CliRunner

from agent_gen.cli import cli
from agent_gen.librarian import HARNESS_ROOT, MANIFEST_FILE, Librarian


def _registry(project: Path) -> dict:
    return json.loads((project / HARNESS_ROOT / MANIFEST_FILE).read_text())["agents"]


def test_agent_commands_target_project_root_not_cwd(tmp_path):
    project, elsewhere = tmp_path / "project", tmp_path / "elsewhere"
    project.mkdir()
    elsewhere.mkdir()
    runner = CliRunner()
    old = os.getcwd()
    os.chdir(elsewhere)
    try:
        assert runner.invoke(cli, ["init", "--project-root", str(project)]).exit_code == 0
        pr = ["--project-root", str(project)]
        r = runner.invoke(cli, ["deploy", "remote-agent", *pr])
        assert r.exit_code == 0, r.output
        assert "remote-agent" in _registry(project)

        r = runner.invoke(cli, ["describe", "remote-agent", "--desc", "Described from elsewhere", *pr])
        assert r.exit_code == 0, r.output
        assert _registry(project)["remote-agent"]["description"] == "Described from elsewhere"

        (project / HARNESS_ROOT / "agents" / "remote-agent" / "docs" / "notes.md").write_text("# notes\n")
        r = runner.invoke(cli, ["audit", "remote-agent", "--fix", *pr])
        assert r.exit_code == 0, r.output
        assert "docs/notes.md" in _registry(project)["remote-agent"]["resources"]["docs"]

        r = runner.invoke(cli, ["wrap", "remote-agent", *pr])
        assert r.exit_code == 0, r.output
        assert list(elsewhere.glob("remote-agent-v*.zip"))  # the bundle is written where you run wrap

        r = runner.invoke(cli, ["uninstall", "remote-agent", *pr], input="y\n")
        assert r.exit_code == 0, r.output
        assert "remote-agent" not in _registry(project)
        assert not (project / HARNESS_ROOT / "agents" / "remote-agent").exists()
        assert not (elsewhere / HARNESS_ROOT).exists()  # nothing was written into the current directory
    finally:
        os.chdir(old)


def test_project_root_must_be_an_initialised_harness(tmp_path):
    runner = CliRunner()
    r = runner.invoke(cli, ["deploy", "x", "--project-root", str(tmp_path)])
    assert r.exit_code != 0
    assert "not an AgentFactory project" in r.output


def test_librarian_knows_its_project(tmp_path):
    agent = tmp_path / "proj" / HARNESS_ROOT / "agents" / "a"
    agent.mkdir(parents=True)
    assert Path(Librarian(str(agent)).project_root) == (tmp_path / "proj").resolve()
    assert Librarian(str(tmp_path / "loose")).project_root == "."
