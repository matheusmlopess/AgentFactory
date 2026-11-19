"""Untrusted agent/skill names, download URLs and workflow shell steps.

Names from bundle manifests, SKILL.md frontmatter and CLI arguments become directory
names that are later passed to rmtree/copytree/move, so they must stay inside the
target directory.
"""

# <!-- version: 1.0.0 -->
import json
import os
import shutil
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from agent_gen.cli import _registry_fetch, _require_safe_url, cli
from agent_gen.librarian import (
    MANIFEST_FILE,
    Librarian,
    _inspect_zip,
    safe_child,
    validate_name,
)

BAD_NAMES = [
    "../evil",
    "..",
    "../../x",
    "/abs/path",
    "a/b",
    "a\\b",
    "",
    ".hidden",
    "-flag",
    "x" * 65,
    "a..b",
    None,
    5,
    ["list"],
]
GOOD_NAMES = ["security-review", "my_skill", "Agent1", "v1.2", "a"]


@pytest.mark.parametrize("name", GOOD_NAMES)
def test_validate_name_accepts_simple_names(name):
    assert validate_name(name) == name


@pytest.mark.parametrize("name", BAD_NAMES)
def test_validate_name_rejects_path_like_names(name):
    with pytest.raises(ValueError, match="Invalid"):
        validate_name(name, "skill")


def test_safe_child_rejects_symlink_escape(tmp_path):
    base = tmp_path / "skills"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (base / "link").symlink_to(outside)
    with pytest.raises(ValueError, match="outside"):
        safe_child(base, "link", "skill")


def _skill_source(tmp_path: Path, name: object) -> Path:
    src = tmp_path / "incoming-skill"
    src.mkdir()
    (src / "skill-manifest.json").write_text(json.dumps({"name": name, "version": "1.0.0"}))
    (src / "SKILL.md").write_text("# skill\n")
    return src


@pytest.mark.parametrize("hostile", ["../../victim", "/tmp/af-victim-abs"])
def test_import_skill_refuses_hostile_name_and_leaves_victim(tmp_path, hostile):
    agent_root = tmp_path / "proj" / ".ai" / "agents" / "a"
    agent_root.mkdir(parents=True)
    victim = tmp_path / "proj" / ".ai" / "victim"
    victim.mkdir()
    (victim / "keep.txt").write_text("keep")
    with (
        patch.object(Librarian, "_validate_and_reconcile_skill_manifest"),
        pytest.raises(ValueError, match="Invalid skill name"),
    ):
        Librarian(str(agent_root)).import_skill(str(_skill_source(tmp_path, hostile)))
    assert (victim / "keep.txt").read_text() == "keep"


def test_import_skill_to_project_refuses_hostile_name(tmp_path):
    project = tmp_path / "proj"
    (project / ".ai").mkdir(parents=True)
    with (
        patch.object(Librarian, "_validate_and_reconcile_skill_manifest"),
        pytest.raises(ValueError, match="Invalid skill name"),
    ):
        Librarian.import_skill_to_project(str(_skill_source(tmp_path, "../escape")), str(project))
    assert not (project / "escape").exists()


def _bundle(path: Path, name: object, extra: dict[str, str] | None = None) -> Path:
    manifest = {
        "name": name,
        "version": "1.0.0",
        "resources": {"skills": [], "commands": [], "docs": [], "scripts": [], "orchestration": []},
    }
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(MANIFEST_FILE, json.dumps(manifest))
        for member, body in (extra or {}).items():
            zf.writestr(member, body)
    return path


def test_cli_import_rejects_traversal_in_bundle_name(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        assert runner.invoke(cli, ["init"]).exit_code == 0
        bundle = _bundle(Path(cwd) / "evil.zip", "../../evil")
        result = runner.invoke(cli, ["import", str(bundle)])
        assert result.exit_code != 0
        assert "Invalid bundle" in result.output
        assert not (Path(cwd) / "evil").exists()
        assert not (Path(cwd) / ".ai" / "evil").exists()


@pytest.mark.parametrize("command", [["uninstall", "../x"], ["describe", "../x", "--desc", "d"], ["deploy", "/abs"]])
def test_cli_name_arguments_are_validated(command):
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init"])
        result = runner.invoke(cli, command)
        assert result.exit_code != 0
        assert "Invalid agent name" in result.output


def test_dry_run_does_not_prompt_for_scripts(tmp_path):
    """#179 gap 4: --dry-run previews instead of asking to proceed."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        runner.invoke(cli, ["init"])
        bundle = _bundle(Path(cwd) / "s.zip", "scripted", {"scripts/run.sh": "#!/bin/sh\necho hi\n"})
        result = runner.invoke(cli, ["import", str(bundle), "--dry-run"], input="")
        assert result.exit_code == 0, result.output
        assert "DRY RUN" in result.output
        assert "Proceed with import?" not in result.output
        assert not (Path(cwd) / ".ai" / "agents" / "scripted").exists()


@pytest.mark.parametrize(
    "steps,flagged",
    [
        ([{"id": "a", "type": "shell", "command": "rm -rf ~"}], True),
        ([{"id": "a", "command": "id"}], True),  # shell is the default step type
        ([{"id": "a", "type": "agent", "prompt": "hi"}], False),
    ],
)
def test_workflow_shell_steps_count_as_executable(tmp_path, steps, flagged):
    wf = json.dumps({"name": "w", "steps": steps})
    bundle = _bundle(tmp_path / "w.zip", "wf-agent", {"orchestration/w.workflow.json": wf})
    info = _inspect_zip(bundle)
    assert ("orchestration/w.workflow.json" in info["executable_files"]) is flagged


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://host/x.zip", "http://evil.example/x.zip", "gopher://x"])
def test_require_safe_url_rejects(url):
    with pytest.raises(click.ClickException, match="only https"):
        _require_safe_url(url, "download URL")


@pytest.mark.parametrize("url", ["https://agentfactory.dev/x.zip", "http://localhost:8000/x.zip", "http://127.0.0.1/x"])
def test_require_safe_url_accepts(url):
    assert _require_safe_url(url, "download URL") == url


def test_registry_fetch_refuses_file_zip_url():
    entry = {"name": "a", "zip_url": "file:///etc/passwd"}
    resp = MagicMock()
    resp.read.return_value = json.dumps(entry).encode()
    resp.__enter__.return_value = resp
    with (
        patch("urllib.request.urlopen", return_value=resp) as urlopen,
        pytest.raises(click.ClickException, match="Refusing download URL"),
    ):
        _registry_fetch("a")
    assert urlopen.call_count == 1  # the entry was fetched, the file:// URL never opened


def test_from_git_accepts_local_directory(tmp_path):
    """#179 gap 2: a local checkout is cloned through a file:// URL."""
    repo = tmp_path / "docs-system"
    repo.mkdir()
    seen = {}

    def fake_run(args, **kw):
        seen["args"] = args
        r = MagicMock()
        r.returncode = 1
        r.stderr = "stop here"
        return r

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["init"])
        with patch("agent_gen.commands._sources.subprocess.run", side_effect=fake_run):
            result = runner.invoke(cli, ["import", "--from-git", str(repo)])
    assert "Invalid git URL" not in result.output
    assert seen["args"][-2] == repo.resolve().as_uri()


def test_migrate_restores_original_when_swap_fails(tmp_path):
    agent = tmp_path / "agent"
    agent.mkdir()
    (agent / MANIFEST_FILE).write_text(json.dumps({"name": "agent"}))
    (agent / "prompt.md").write_text("original")
    real_move = shutil.move

    def failing_move(src, dst, *a, **kw):
        if os.path.abspath(dst) == str(agent.resolve()):
            raise OSError("disk full")
        return real_move(src, dst, *a, **kw)

    with (
        patch("agent_gen.core.retrofit.shutil.move", side_effect=failing_move),
        pytest.raises(RuntimeError, match="rolled back"),
    ):
        Librarian(str(agent)).migrate({"prompt.md": "docs"})
    assert (agent / "prompt.md").read_text() == "original"
    assert not any(p.name.endswith(".pre-migrate") for p in tmp_path.iterdir())


def test_migrate_still_works(tmp_path):
    agent = tmp_path / "agent"
    agent.mkdir()
    (agent / MANIFEST_FILE).write_text(json.dumps({"name": "agent"}))
    (agent / "prompt.md").write_text("x")
    Librarian(str(agent)).migrate({"prompt.md": "docs"})
    assert (agent / "docs" / "prompt.md").exists()
    assert not (tmp_path / ".agent.pre-migrate").exists()


# ---------------------------------------------------------------- #179 gap 1: honor the repo's own manifest


def _git(cwd, *args):
    import subprocess

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.test",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.test",
    }
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=env)


def _agent_repo(tmp_path: Path, layout: str) -> Path:
    """A git repo that ships a full Portable Unit (like docs-system) under agent/ or at the root."""
    repo = tmp_path / "docs-system"
    unit = repo / "agent" if layout == "agent" else repo
    files = {
        "skills/docs-system/SKILL.md": "---\nname: docs-system\ndescription: d\n---\n# Docs\n",
        "commands/docs-plan.md": "# plan\n",
        "docs/SKILL-DOCS-SYSTEM.md": "# guide\n",
        "scripts/docs-plan.sh": "#!/bin/sh\necho plan\n",
    }
    for rel, body in files.items():
        write = unit / rel
        write.parent.mkdir(parents=True, exist_ok=True)
        write.write_text(body)
    manifest = {
        "name": "docs-system",
        "version": "1.0.2",
        "description": "Documentation agent",
        "resources": {
            "skills": ["skills/docs-system/SKILL.md"],
            "commands": ["commands/docs-plan.md"],
            "docs": ["docs/SKILL-DOCS-SYSTEM.md"],
            "scripts": ["scripts/docs-plan.sh"],
            "orchestration": [],
        },
        "dependencies": {},
    }
    (unit / MANIFEST_FILE).write_text(json.dumps(manifest))
    (repo / "README.md").write_text("# docs-system\n")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


@pytest.mark.parametrize("layout", ["agent", "root"])
def test_from_git_imports_the_declared_unit(tmp_path, layout):
    repo = _agent_repo(tmp_path, layout)
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        assert runner.invoke(cli, ["init"]).exit_code == 0
        r = runner.invoke(cli, ["import", "--from-git", str(repo), "--allow-scripts"])
        assert r.exit_code == 0, r.output
        assert "importing it as declared" in r.output
        dest = Path(cwd) / ".ai" / "agents" / "docs-system"
        for rel in (
            "skills/docs-system/SKILL.md",
            "commands/docs-plan.md",
            "docs/SKILL-DOCS-SYSTEM.md",
            "scripts/docs-plan.sh",
        ):
            assert (dest / rel).is_file(), rel
        assert json.loads((dest / MANIFEST_FILE).read_text())["version"] == "1.0.2"


def test_from_git_incomplete_manifest_is_a_clear_error(tmp_path):
    repo = _agent_repo(tmp_path, "agent")
    (repo / "agent" / "commands" / "docs-plan.md").unlink()
    _git(repo, "commit", "-qam", "drop a file")
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["init"])
        r = runner.invoke(cli, ["import", "--from-git", str(repo), "--allow-scripts"])
        assert r.exit_code != 0
        assert "incomplete" in r.output and "commands/docs-plan.md" in r.output


# ---------------------------------------------------------------- #146: import is all-or-nothing


def test_import_rolls_back_when_registration_fails(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        assert runner.invoke(cli, ["init"]).exit_code == 0
        global_manifest = Path(cwd) / ".ai" / MANIFEST_FILE
        before = global_manifest.read_text()
        bundle = _bundle(Path(cwd) / "ok.zip", "rollback-agent")
        with patch.object(Librarian, "register_in_project", side_effect=OSError("disk full")):
            r = runner.invoke(cli, ["import", str(bundle)])
        assert r.exit_code != 0
        assert "rolled back" in r.output
        assert not (Path(cwd) / ".ai" / "agents" / "rollback-agent").exists()
        assert json.loads(global_manifest.read_text()) == json.loads(before)
        # A clean retry still works afterwards.
        r = runner.invoke(cli, ["import", str(bundle)])
        assert r.exit_code == 0, r.output
        assert "rollback-agent" in json.loads(global_manifest.read_text())["agents"]


def test_registry_import_records_source_before_the_move(tmp_path):
    runner = CliRunner()
    buf_path = tmp_path / "reg.zip"
    _bundle(buf_path, "reg-src")
    entry = {
        "name": "reg-src",
        "version": "1.0.0",
        "zip_url": "https://x/reg.zip",
        "sha256": __import__("hashlib").sha256(buf_path.read_bytes()).hexdigest(),
    }
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        runner.invoke(cli, ["init"])
        with patch("agent_gen.commands._remote._registry_fetch", return_value=(entry, buf_path.read_bytes())):
            r = runner.invoke(cli, ["import", "--from-registry", "reg-src"])
        assert r.exit_code == 0, r.output
        data = json.loads((Path(cwd) / ".ai" / "agents" / "reg-src" / MANIFEST_FILE).read_text())
        assert data["source"] == {"registry": "reg-src"}
