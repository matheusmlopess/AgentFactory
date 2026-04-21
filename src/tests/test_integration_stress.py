"""
FormatSwitch integration stress tests.

These tests exercise every meaningful execution path of the FormatSwitch
system end-to-end using Click's isolated_filesystem — no mocks, no stubs.

They run automatically in CI (every push/PR) as part of the standard test
matrix and are also enforced as a required gate in release.yml before any
wheel is built or published to PyPI.

To run only integration tests locally:
    pytest -m integration -v

To skip integration tests (quick unit-only run):
    pytest -m "not integration" -v

Coverage scope: init --primary flags, adapter add (mid-project activation,
idempotency, error paths), brief command, skill/command/agent/rule
propagation to all three CLI formats, hash-before-write, legacy symlink
migration, deploy registration, full lifecycle, registry integrity, and
empty-input formatter robustness.
"""
import json
import os
import time
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_gen.cli import cli
from agent_gen.librarian import (
    Librarian,
    HARNESS_ROOT,
    _FORMAT_REGISTRY,
    _FORMATTER_DISPATCH,
    _fmt_skills_table,
    _fmt_skills_blocks,
    _fmt_skills_tools,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def runner():
    return CliRunner()


def _add_skill(root: Path, name: str, desc: str = "", triggers: str = "",
               input_hint: str = "") -> None:
    """Helper — write a skill-manifest.json into the harness skills dir."""
    sd = root / HARNESS_ROOT / "skills" / name
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "skill-manifest.json").write_text(
        json.dumps({"name": name, "description": desc,
                    "triggers": triggers, "input": input_hint}),
        encoding="utf-8",
    )


def _add_rule(root: Path, name: str, body: str) -> None:
    (root / HARNESS_ROOT / "rules" / f"{name}.md").write_text(
        f"# {name}\n\n{body}", encoding="utf-8"
    )


def _add_command(root: Path, name: str, desc: str = "No description") -> None:
    (root / HARNESS_ROOT / "commands" / f"{name}.md").write_text(
        f"---\ndescription: {desc}\n---\n# {name}\n\nCommand body.",
        encoding="utf-8",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Init — default (claude primary)
# ─────────────────────────────────────────────────────────────────────────────

class TestInitDefaultPrimary:
    """agentfactory-gen init with no --primary flag (defaults to claude)."""

    def test_exit_zero(self, runner):
        with runner.isolated_filesystem():
            r = runner.invoke(cli, ["init"])
            assert r.exit_code == 0, r.output

    def test_claude_symlink_created(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            assert Path("CLAUDE.md").is_symlink()

    def test_claude_symlink_target(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            target = os.readlink("CLAUDE.md")
            assert "claude" in target and "brief.md" in target

    def test_all_adapter_root_files_created(self, runner):
        """init creates root symlinks for all adapters since all briefs compile (#120)."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            assert Path("AGENTS.md").is_symlink()
            assert Path("CODEX.md").is_symlink()
            assert Path("GEMINI.md").is_symlink()
            assert Path("CLAUDE.md").is_symlink()

    def test_folder_symlinks_all_created(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            assert Path(".claude").is_symlink()
            assert Path(".codex").is_symlink()
            assert Path(".gemini").is_symlink()

    def test_all_adapter_briefs_compiled(self, runner):
        """All adapter dirs exist after init, so all briefs are compiled."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            for adapter in ["claude", "codex", "gemini"]:
                assert Path(f".ai/adapters/{adapter}/brief.md").exists(), \
                    f"brief.md missing for {adapter}"

    def test_codex_skills_symlink_fixed(self, runner):
        """#94: codex/skills symlink created after init."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            assert Path(".ai/adapters/codex/skills").is_symlink()

    def test_claude_brief_has_skills_section(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            b = Path(".ai/adapters/claude/brief.md").read_text()
            assert "## Available Skills" in b

    def test_codex_brief_no_table_format(self, runner):
        """Codex does not use | Skill | table format."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            b = Path(".ai/adapters/codex/brief.md").read_text()
            assert "| Skill |" not in b

    def test_gemini_brief_has_tools_header(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            b = Path(".ai/adapters/gemini/brief.md").read_text()
            assert "## Available Tools" in b

    def test_all_briefs_have_adapter_annotation(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            for adapter in ["claude", "codex", "gemini"]:
                b = Path(f".ai/adapters/{adapter}/brief.md").read_text()
                assert f"@adapter: {adapter}" in b

    def test_all_briefs_have_recompile_hint(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            for adapter in ["claude", "codex", "gemini"]:
                b = Path(f".ai/adapters/{adapter}/brief.md").read_text()
                assert "@recompile: agentfactory-gen brief" in b


# ─────────────────────────────────────────────────────────────────────────────
# 2. Init — alternate primary flags
# ─────────────────────────────────────────────────────────────────────────────

class TestInitAlternatePrimary:

    def test_codex_primary_sets_agents_md(self, runner):
        """#93: AGENTS.md routes to codex/brief.md when primary=codex."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "codex"])
            assert Path("AGENTS.md").is_symlink()
            target = os.readlink("AGENTS.md")
            assert "codex" in target and "brief.md" in target

    def test_codex_primary_sets_codex_md(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "codex"])
            assert Path("CODEX.md").is_symlink()
            assert "codex" in os.readlink("CODEX.md")

    def test_codex_primary_creates_all_root_files(self, runner):
        """--primary codex still creates CLAUDE.md and GEMINI.md (all briefs compile)."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "codex"])
            assert Path("CLAUDE.md").is_symlink()
            assert Path("AGENTS.md").is_symlink()
            assert Path("GEMINI.md").is_symlink()

    def test_codex_brief_no_commands_section(self, runner):
        """Codex format omits commands — they'd need / prefix which Codex doesn't use."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "codex"])
            b = Path(".ai/adapters/codex/brief.md").read_text()
            assert "## Commands" not in b

    def test_gemini_primary_sets_gemini_md(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "gemini"])
            assert Path("GEMINI.md").is_symlink()
            assert "gemini" in os.readlink("GEMINI.md")

    def test_gemini_primary_creates_all_root_files(self, runner):
        """--primary gemini still creates CLAUDE.md and AGENTS.md (all briefs compile)."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "gemini"])
            assert Path("CLAUDE.md").is_symlink()
            assert Path("AGENTS.md").is_symlink()
            assert Path("GEMINI.md").is_symlink()

    def test_unknown_primary_fails(self, runner):
        with runner.isolated_filesystem():
            r = runner.invoke(cli, ["init", "--primary", "cursor"])
            assert r.exit_code != 0


# ─────────────────────────────────────────────────────────────────────────────
# 3. adapter add
# ─────────────────────────────────────────────────────────────────────────────

class TestAdapterAdd:

    def test_codex_add_creates_dir_and_brief(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "claude"])
            r = runner.invoke(cli, ["adapter", "add", "codex"])
            assert r.exit_code == 0, r.output
            assert Path(".ai/adapters/codex").is_dir()
            assert Path(".ai/adapters/codex/brief.md").exists()

    def test_codex_add_creates_root_symlinks(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "claude"])
            runner.invoke(cli, ["adapter", "add", "codex"])
            assert Path("AGENTS.md").is_symlink()
            assert Path("CODEX.md").is_symlink()
            assert "codex" in os.readlink("AGENTS.md")

    def test_codex_add_creates_skills_symlink(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "claude"])
            runner.invoke(cli, ["adapter", "add", "codex"])
            assert Path(".ai/adapters/codex/skills").is_symlink()
            assert os.readlink(".ai/adapters/codex/skills") == "../../skills"

    def test_codex_add_writes_config(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "claude"])
            runner.invoke(cli, ["adapter", "add", "codex"])
            config_path = Path(".ai/adapters/codex/config.toml")
            assert config_path.exists()
            assert 'model = "gpt-5.4"' in config_path.read_text(encoding="utf-8")

    def test_gemini_add_creates_tools_symlink(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "claude"])
            runner.invoke(cli, ["adapter", "add", "gemini"])
            assert Path(".ai/adapters/gemini/tools").is_symlink()

    def test_gemini_add_sets_gemini_md(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "claude"])
            runner.invoke(cli, ["adapter", "add", "gemini"])
            assert Path("GEMINI.md").is_symlink()
            assert "gemini" in os.readlink("GEMINI.md")

    def test_add_idempotent_does_not_overwrite_config(self, runner):
        """Re-running adapter add preserves user-edited config files."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "claude"])
            runner.invoke(cli, ["adapter", "add", "codex"])
            cfg = Path(".ai/adapters/codex/config.toml")
            cfg.write_text("[custom]\nsecret = true\n", encoding="utf-8")
            r2 = runner.invoke(cli, ["adapter", "add", "codex"])
            assert r2.exit_code == 0, r2.output
            assert "secret = true" in cfg.read_text()

    def test_add_idempotent_recompiles_brief(self, runner):
        """Re-running adapter add refreshes the brief (e.g. after skill import)."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "claude"])
            runner.invoke(cli, ["adapter", "add", "codex"])
            time.sleep(0.05)
            _add_skill(Path("."), "new-skill", "A fresh skill")
            r = runner.invoke(cli, ["adapter", "add", "codex"])
            assert r.exit_code == 0
            assert "new-skill" in Path(".ai/adapters/codex/brief.md").read_text()

    def test_add_unknown_adapter_fails(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            r = runner.invoke(cli, ["adapter", "add", "foobar"])
            assert r.exit_code != 0

    def test_add_no_harness_fails(self, runner):
        with runner.isolated_filesystem():
            r = runner.invoke(cli, ["adapter", "add", "claude"])
            assert r.exit_code != 0
            assert any(w in r.output.lower() for w in ["harness", "init"])

    def test_add_skips_non_symlink_root_file(self, runner):
        """A real file at AGENTS.md is never clobbered by adapter add codex."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "claude"])
            # Replace the symlink created by init with a real file
            if Path("AGENTS.md").is_symlink():
                Path("AGENTS.md").unlink()
            Path("AGENTS.md").write_text("# Custom\n")
            r = runner.invoke(cli, ["adapter", "add", "codex"])
            assert r.exit_code == 0
            assert not Path("AGENTS.md").is_symlink()
            assert "Custom" in Path("AGENTS.md").read_text()

    def test_add_symlinks_only_after_compile(self, runner):
        """Root symlinks created only after brief.md is successfully compiled."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "claude"])
            r = runner.invoke(cli, ["adapter", "add", "gemini"])
            assert r.exit_code == 0
            assert Path(".ai/adapters/gemini/brief.md").exists()
            assert Path("GEMINI.md").is_symlink()


# ─────────────────────────────────────────────────────────────────────────────
# 4. brief command
# ─────────────────────────────────────────────────────────────────────────────

class TestBriefCommand:

    def test_brief_no_harness_fails(self, runner):
        with runner.isolated_filesystem():
            r = runner.invoke(cli, ["brief"])
            assert r.exit_code != 0

    def test_brief_reports_all_adapters(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            r = runner.invoke(cli, ["brief"])
            assert r.exit_code == 0, r.output
            assert "claude" in r.output
            assert "codex" in r.output
            assert "gemini" in r.output
            assert "AgentFactory.md" in r.output

    def test_brief_quiet_no_output(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            r = runner.invoke(cli, ["-q", "brief"])
            assert r.exit_code == 0
            assert r.output.strip() == ""


# ─────────────────────────────────────────────────────────────────────────────
# 5. Skills — format fidelity across all three CLIs
# ─────────────────────────────────────────────────────────────────────────────

class TestSkillsPropagation:

    def _setup(self, runner):
        runner.invoke(cli, ["init"])
        runner.invoke(cli, ["adapter", "add", "codex"])
        runner.invoke(cli, ["adapter", "add", "gemini"])
        _add_skill(Path("."), "my-workflow",
                   desc="Automate complex workflows",
                   triggers="when you need to automate",
                   input_hint="task description string")
        runner.invoke(cli, ["brief"])

    def test_claude_skill_in_table(self, runner):
        with runner.isolated_filesystem():
            self._setup(runner)
            b = Path(".ai/adapters/claude/brief.md").read_text()
            assert "| my-workflow |" in b

    def test_claude_skill_path_format(self, runner):
        with runner.isolated_filesystem():
            self._setup(runner)
            b = Path(".ai/adapters/claude/brief.md").read_text()
            assert ".claude/skills/my-workflow/SKILL.md" in b

    def test_codex_skill_in_blocks(self, runner):
        with runner.isolated_filesystem():
            self._setup(runner)
            b = Path(".ai/adapters/codex/brief.md").read_text()
            assert "### my-workflow" in b
            assert "- Description: Automate complex workflows" in b
            assert "- Use when: when you need to automate" in b

    def test_codex_skill_path_format(self, runner):
        with runner.isolated_filesystem():
            self._setup(runner)
            b = Path(".ai/adapters/codex/brief.md").read_text()
            assert ".codex/skills/my-workflow/SKILL.md" in b

    def test_gemini_skill_in_tools(self, runner):
        with runner.isolated_filesystem():
            self._setup(runner)
            b = Path(".ai/adapters/gemini/brief.md").read_text()
            assert "### my-workflow" in b
            assert "- Input: task description string" in b

    def test_gemini_skill_path_format(self, runner):
        with runner.isolated_filesystem():
            self._setup(runner)
            b = Path(".ai/adapters/gemini/brief.md").read_text()
            assert ".gemini/tools/my-workflow/SKILL.md" in b

    def test_gemini_input_fallback_to_triggers(self, runner):
        """When 'input' field absent, Gemini brief falls back to 'triggers'."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            runner.invoke(cli, ["adapter", "add", "gemini"])
            _add_skill(Path("."), "fallback-skill",
                       desc="desc", triggers="trigger text")
            runner.invoke(cli, ["brief"])
            b = Path(".ai/adapters/gemini/brief.md").read_text()
            assert "trigger text" in b

    def test_skill_without_manifest_uses_dir_name(self, runner):
        """Skill dir with no skill-manifest.json: dir name used as fallback."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            Path(".ai/skills/bare-skill").mkdir(parents=True)
            runner.invoke(cli, ["brief"])
            b = Path(".ai/adapters/claude/brief.md").read_text()
            assert "bare-skill" in b

    def test_new_skill_via_import_skill_updates_all_briefs(self, runner):
        """import-skill triggers brief recompile across all active adapters."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            runner.invoke(cli, ["adapter", "add", "codex"])
            runner.invoke(cli, ["adapter", "add", "gemini"])
            with tempfile.TemporaryDirectory() as sd:
                skill_dir = Path(sd) / "imported-skill"
                skill_dir.mkdir()
                (skill_dir / "SKILL.md").write_text("# imported-skill\n\nDoes things.")
                (skill_dir / "skill-manifest.json").write_text(json.dumps({
                    "name": "imported-skill",
                    "version": "1.0.0",
                    "description": "Does things",
                    "triggers": "always",
                }))
                r = runner.invoke(cli, ["import-skill", str(skill_dir)])
            assert r.exit_code == 0, r.output
            for adapter in ["claude", "codex", "gemini"]:
                b = Path(f".ai/adapters/{adapter}/brief.md").read_text()
                assert "imported-skill" in b, \
                    f"imported-skill missing from {adapter} brief"


# ─────────────────────────────────────────────────────────────────────────────
# 6. Commands — Claude only, / prefix
# ─────────────────────────────────────────────────────────────────────────────

class TestCommandsPropagation:

    def _setup(self, runner):
        runner.invoke(cli, ["init"])
        runner.invoke(cli, ["adapter", "add", "codex"])
        runner.invoke(cli, ["adapter", "add", "gemini"])
        _add_command(Path("."), "git-workflow", "Git workflow helper")
        runner.invoke(cli, ["brief"])

    def test_claude_has_commands_section(self, runner):
        with runner.isolated_filesystem():
            self._setup(runner)
            b = Path(".ai/adapters/claude/brief.md").read_text()
            assert "## Commands" in b

    def test_claude_command_has_slash_prefix(self, runner):
        with runner.isolated_filesystem():
            self._setup(runner)
            b = Path(".ai/adapters/claude/brief.md").read_text()
            assert "`/git-workflow`" in b

    def test_codex_no_commands_section(self, runner):
        with runner.isolated_filesystem():
            self._setup(runner)
            b = Path(".ai/adapters/codex/brief.md").read_text()
            assert "## Commands" not in b

    def test_gemini_no_commands_section(self, runner):
        with runner.isolated_filesystem():
            self._setup(runner)
            b = Path(".ai/adapters/gemini/brief.md").read_text()
            assert "## Commands" not in b


# ─────────────────────────────────────────────────────────────────────────────
# 7. Agents and rules in all briefs
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentsAndRules:

    def test_deployed_agent_appears_in_all_briefs(self, runner):
        """deploy now auto-registers in global manifest → appears in all briefs."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            runner.invoke(cli, ["adapter", "add", "codex"])
            runner.invoke(cli, ["adapter", "add", "gemini"])
            runner.invoke(cli, ["deploy", "my-agent"])
            runner.invoke(cli, ["describe", "my-agent", "--desc", "Does great things"])
            for adapter in ["claude", "codex", "gemini"]:
                b = Path(f".ai/adapters/{adapter}/brief.md").read_text()
                assert "my-agent" in b, f"my-agent missing from {adapter}"
                assert "Does great things" in b, \
                    f"description missing from {adapter}"

    def test_rules_appear_in_all_briefs(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            runner.invoke(cli, ["adapter", "add", "codex"])
            runner.invoke(cli, ["adapter", "add", "gemini"])
            _add_rule(Path("."), "tdd",
                      "- Always write tests before writing implementation code.")
            runner.invoke(cli, ["brief"])
            for adapter in ["claude", "codex", "gemini"]:
                b = Path(f".ai/adapters/{adapter}/brief.md").read_text()
                assert "Always write tests before writing implementation" in b, \
                    f"rule missing from {adapter}"

    def test_skill_briefing_rule_appears_in_all_briefs(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            runner.invoke(cli, ["adapter", "add", "codex"])
            runner.invoke(cli, ["adapter", "add", "gemini"])
            _add_rule(
                Path("."),
                "skill-briefing",
                "- **Skill Briefing:** Keep description brief and triggers concise for compiled briefs.",
            )
            runner.invoke(cli, ["brief"])
            for adapter in ["claude", "codex", "gemini"]:
                b = Path(f".ai/adapters/{adapter}/brief.md").read_text(encoding="utf-8")
                assert "Keep description brief and triggers concise for compiled briefs." in b, \
                    f"skill briefing rule missing from {adapter}"

    def test_skill_manifest_brief_metadata_appears_in_codex_brief(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            runner.invoke(cli, ["adapter", "add", "codex"])
            _add_skill(
                Path("."),
                "brief-skill",
                "Short brief-safe summary.",
                "when you need a concise workflow hint",
            )
            runner.invoke(cli, ["brief"])
            brief = Path(".ai/adapters/codex/brief.md").read_text(encoding="utf-8")
            assert "- Description: Short brief-safe summary." in brief
            assert "- Use when: when you need a concise workflow hint" in brief


# ─────────────────────────────────────────────────────────────────────────────
# 8. Hash-before-write
# ─────────────────────────────────────────────────────────────────────────────

class TestHashBeforeWrite:

    def test_unchanged_brief_not_rewritten(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            bp = Path(".ai/adapters/claude/brief.md")
            mtime1 = bp.stat().st_mtime
            runner.invoke(cli, ["brief"])
            mtime2 = bp.stat().st_mtime
            assert mtime1 == mtime2, \
                "brief.md was rewritten when content had not changed"

    def test_changed_brief_is_rewritten(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            bp = Path(".ai/adapters/claude/brief.md")
            mtime1 = bp.stat().st_mtime
            time.sleep(0.05)  # ensure mtime resolution shows a change
            _add_skill(Path("."), "new-skill", "A brand new skill")
            runner.invoke(cli, ["brief"])
            mtime2 = bp.stat().st_mtime
            assert mtime1 != mtime2, \
                "brief.md was NOT rewritten after adding a new skill"


# ─────────────────────────────────────────────────────────────────────────────
# 9. Legacy symlink migration
# ─────────────────────────────────────────────────────────────────────────────

class TestLegacyMigration:

    def _make_legacy_harness(self):
        """Simulate a pre-FormatSwitch project state (all links → AgentFactory.md)."""
        for d in ["adapters/claude", "adapters/codex", "adapters/gemini",
                  "skills", "commands", "rules", "agents", "memory"]:
            Path(f".ai/{d}").mkdir(parents=True, exist_ok=True)
        Path(".ai/AgentFactory.md").write_text(
            "# Context\n<!-- @agent-registry:start -->\n<!-- @agent-registry:end -->\n"
        )
        Path(".ai/agent-manifest.json").write_text('{"factory":"AF","agents":{}}')

    def test_migration_updates_legacy_links(self, runner):
        with runner.isolated_filesystem():
            self._make_legacy_harness()
            os.symlink(".ai/AgentFactory.md", "CLAUDE.md")
            os.symlink(".ai/AgentFactory.md", "AGENTS.md")
            os.symlink(".ai/AgentFactory.md", "GEMINI.md")
            Librarian.update_harness_files(".")
            for f, expected_adapter in [("CLAUDE.md", "claude"),
                                        ("AGENTS.md", "codex"),
                                        ("GEMINI.md", "gemini")]:
                target = os.readlink(f)
                assert "brief.md" in target, f"{f} not migrated to brief.md"
                assert expected_adapter in target, \
                    f"{f} target doesn't contain {expected_adapter}"

    def test_migration_skips_if_brief_missing(self, runner):
        """No brief compiled → legacy symlink is NOT updated (no dangling link)."""
        with runner.isolated_filesystem():
            Path(".ai/adapters/claude").mkdir(parents=True, exist_ok=True)
            Path(".ai/skills").mkdir(parents=True, exist_ok=True)
            os.symlink(".ai/AgentFactory.md", "CLAUDE.md")
            Librarian._migrate_root_symlinks(".")
            assert "AgentFactory.md" in os.readlink("CLAUDE.md")

    def test_migration_skips_custom_symlinks(self, runner):
        """Symlinks pointing to something other than AgentFactory.md are untouched."""
        with runner.isolated_filesystem():
            self._make_legacy_harness()
            Librarian._compile_adapter_briefs(".")
            os.symlink("custom/my-file.md", "CLAUDE.md")
            Librarian._migrate_root_symlinks(".")
            assert os.readlink("CLAUDE.md") == "custom/my-file.md"

    def test_migration_via_brief_command(self, runner):
        """Running `brief` on a legacy project migrates all root symlinks."""
        with runner.isolated_filesystem():
            self._make_legacy_harness()
            os.symlink(".ai/AgentFactory.md", "CLAUDE.md")
            Librarian.update_harness_files(".")
            target = os.readlink("CLAUDE.md")
            assert "brief.md" in target


# ─────────────────────────────────────────────────────────────────────────────
# 10. Full lifecycle — deploy → describe → wrap → brief
# ─────────────────────────────────────────────────────────────────────────────

class TestFullLifecycle:

    def test_deploy_then_wrap_agent_in_briefs(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            runner.invoke(cli, ["adapter", "add", "codex"])
            runner.invoke(cli, ["deploy", "lifecycle-agent"])
            runner.invoke(cli, ["describe", "lifecycle-agent",
                                "--desc", "A lifecycle test agent"])
            Path(".ai/agents/lifecycle-agent/skills/test.md").write_text("# test")
            runner.invoke(cli, ["wrap", "lifecycle-agent"])
            for adapter in ["claude", "codex"]:
                b = Path(f".ai/adapters/{adapter}/brief.md").read_text()
                assert "lifecycle-agent" in b, \
                    f"lifecycle-agent missing from {adapter} after wrap"

    def test_codex_then_claude_activation(self, runner):
        """Start with codex primary — all root files exist; claude symlink verified."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "codex"])
            assert Path("AGENTS.md").is_symlink()
            # CLAUDE.md is created on init (all adapters compile)
            assert Path("CLAUDE.md").is_symlink()
            assert "claude" in os.readlink("CLAUDE.md")
            # AGENTS.md points to codex
            assert "codex" in os.readlink("AGENTS.md")


# ─────────────────────────────────────────────────────────────────────────────
# 11. Wiring correctness
# ─────────────────────────────────────────────────────────────────────────────

class TestAdapterWiring:

    def test_claude_skills_and_commands_wired(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            ai = Path(".ai/adapters")
            assert (ai / "claude" / "skills").is_symlink()
            assert (ai / "claude" / "commands").is_symlink()

    def test_gemini_tools_wired_to_skills(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            link = Path(".ai/adapters/gemini/tools")
            assert link.is_symlink()
            assert os.readlink(str(link)) == "../../skills"

    def test_codex_prompts_and_skills_wired(self, runner):
        """#94: Codex gets both prompts (→ commands) and skills (→ skills)."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            ai = Path(".ai/adapters/codex")
            assert (ai / "prompts").is_symlink()
            assert os.readlink(str(ai / "prompts")) == "../../commands"
            assert (ai / "skills").is_symlink()
            assert os.readlink(str(ai / "skills")) == "../../skills"


# ─────────────────────────────────────────────────────────────────────────────
# 12. Registry integrity and formatter robustness
# ─────────────────────────────────────────────────────────────────────────────

class TestRegistryIntegrity:

    _REQUIRED_KEYS = [
        "output", "header", "root_files", "folder_symlink", "wiring",
        "config_file", "config_default", "skill_path_template",
        "command_prefix", "sections", "section_order",
    ]

    def test_all_required_keys_present(self):
        for adapter, config in _FORMAT_REGISTRY.items():
            for key in self._REQUIRED_KEYS:
                assert key in config, \
                    f"_FORMAT_REGISTRY['{adapter}'] missing required key '{key}'"

    def test_all_referenced_formatters_exist(self):
        for adapter, config in _FORMAT_REGISTRY.items():
            for section_key, fn_name in config["sections"].items():
                if fn_name is None:
                    continue
                assert fn_name in _FORMATTER_DISPATCH, \
                    (f"_FORMAT_REGISTRY['{adapter}']['sections']['{section_key}'] "
                     f"references unknown formatter '{fn_name}'")

    def test_formatters_handle_empty_input(self):
        empty_cfg = {"skill_path_template": ".cli/{name}/SKILL.md",
                     "command_prefix": "/"}
        for fn in [_fmt_skills_table, _fmt_skills_blocks, _fmt_skills_tools]:
            result = fn([], empty_cfg)
            assert isinstance(result, str), f"{fn.__name__} must return str"
            assert len(result) > 0, f"{fn.__name__} returned empty string"
            assert "#" in result, f"{fn.__name__} output has no markdown heading"
