"""#189: librarian.py split into agent_gen.core — the public surface, logging and the zip inspection fix."""

import json
import zipfile
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from agent_gen import librarian
from agent_gen.cli import cli
from agent_gen.librarian import Librarian, _inspect_zip

OLD_TOP_LEVEL = [
    "CONTEXT_FILE",
    "CONVERSION_PROFILES",
    "HARNESS_ROOT",
    "Librarian",
    "MANIFEST_FILE",
    "TRACKED_DIRS",
    "_FORMATTER_DISPATCH",
    "_FORMAT_REGISTRY",
    "_NAME_RE",
    "_atomic_write_json",
    "_collect_project_context",
    "_extract_first_paragraph",
    "_fit_context_to_budget",
    "_fmt_agents_list",
    "_fmt_commands_list",
    "_fmt_harness_identity",
    "_fmt_rules_list",
    "_fmt_skills_blocks",
    "_fmt_skills_table",
    "_fmt_skills_tools",
    "_git_ref",
    "_inspect_zip",
    "_run_preamble_oracle",
    "_safe_extract",
    "_sanitize_for_markdown",
    "_workflow_has_shell_steps",
    "safe_child",
    "validate_name",
]
OLD_METHODS = [
    "__init__",
    "_analyze_dependencies",
    "_auto_init_agent_manifest",
    "_auto_stub_skill_manifests",
    "_check_repo_state",
    "_collect_agents_data",
    "_collect_commands_data",
    "_collect_rules_data",
    "_collect_skills_data",
    "_compile_adapter_briefs",
    "_compile_agentfactory_md",
    "_crawl_resources",
    "_ensure_adapter_wiring",
    "_extract_first_bullet_or_line",
    "_extract_first_description",
    "_extract_source_context",
    "_get_lock",
    "_global_manifest_path",
    "_load_manifest",
    "_migrate_root_symlinks",
    "_parse_skill_manifests",
    "_parse_skill_md_frontmatter",
    "_parse_skill_md_version",
    "_render_brief",
    "_save_manifest",
    "_validate_and_reconcile_skill_manifest",
    "audit",
    "deregister_from_project",
    "import_skill",
    "import_skill_to_project",
    "init",
    "migrate",
    "propose_retrofit",
    "register_in_project",
    "sync",
    "sync_to_global",
    "uninstall",
    "unpack",
    "update_harness_files",
    "validate",
    "wrap",
]


def test_every_old_top_level_name_is_still_importable():
    missing = [n for n in OLD_TOP_LEVEL if not hasattr(librarian, n)]
    assert missing == []


def test_librarian_keeps_every_method():
    assert [m for m in OLD_METHODS if not hasattr(Librarian, m)] == []


def test_unreadable_zip_member_is_treated_as_executable(tmp_path):
    z = tmp_path / "u.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("agent-manifest.json", json.dumps({"name": "u", "version": "1.0.0"}))
        zf.writestr("commands/run.md", "harmless")
    real_open = zipfile.ZipFile.open

    def flaky_open(self, name, *a, **kw):
        if name == "commands/run.md":
            raise RuntimeError("encrypted member")
        return real_open(self, name, *a, **kw)

    with patch.object(zipfile.ZipFile, "open", flaky_open):
        info = _inspect_zip(z)
    assert "commands/run.md" in info["executable_files"]


def test_library_warnings_reach_the_cli_and_quiet_hides_them(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        assert runner.invoke(cli, ["init"]).exit_code == 0
        with patch.object(Librarian, "_render_brief", side_effect=RuntimeError("boom")):
            loud = runner.invoke(cli, ["brief"])
            quiet = runner.invoke(cli, ["-q", "brief"])
    assert "failed to compile brief" in loud.output and "boom" in loud.output
    assert "failed to compile brief" not in quiet.output


def test_core_modules_stay_small():
    core = Path(librarian.__file__).parent / "core"
    sizes = {p.name: len(p.read_text().splitlines()) for p in core.glob("*.py")}
    assert max(sizes.values()) <= 500, sizes
