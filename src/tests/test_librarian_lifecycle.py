import io
import json
import os
import stat
import unittest
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from agent_gen.librarian import (
    Librarian, MANIFEST_FILE, HARNESS_ROOT, CONTEXT_FILE, _safe_extract,
)

class TestLibrarianLifecycle(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.test_dir.name)
        
        self.agents_dir = self.project_root / "agents"
        self.agents_dir.mkdir()
        
        # Mock global manifest
        self.global_manifest_path = self.project_root / MANIFEST_FILE
        self.global_manifest = {
            "factory": "AgentFactory",
            "agents": {
                "mock-agent": {
                    "version": "1.0.0",
                    "resources": {}
                }
            }
        }
        with open(self.global_manifest_path, "w") as f:
            json.dump(self.global_manifest, f)
            
        # Mock harness files
        (self.project_root / "CLAUDE.md").write_text("<!-- @agent-registry:start -->\n<!-- @agent-registry:end -->")
        
        # Mock an installed agent
        self.mock_agent_dir = self.agents_dir / "mock-agent"
        self.mock_agent_dir.mkdir()
        
        # Create standard dirs and manifest for the agent
        (self.mock_agent_dir / "skills").mkdir()
        (self.mock_agent_dir / "scripts").mkdir()
        
        agent_manifest = {
            "name": "mock-agent",
            "version": "1.0.0",
            "resources": {"skills": [], "scripts": []}
        }
        with open(self.mock_agent_dir / MANIFEST_FILE, "w") as f:
            json.dump(agent_manifest, f)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_uninstall_removes_agent_and_deregisters(self):
        librarian = Librarian(str(self.mock_agent_dir))
        
        # Call uninstall
        librarian.uninstall(str(self.project_root))
        
        # 1. Directory is gone
        self.assertFalse(self.mock_agent_dir.exists())
        
        # 2. Deregistered from global manifest
        with open(self.global_manifest_path) as f:
            global_manifest = json.load(f)
        self.assertNotIn("mock-agent", global_manifest.get("agents", {}))

    def test_import_unpacks_and_registers(self):
        # Create a valid portable bundle zip
        bundle_path = self.project_root / "new-agent-v1.zip"
        
        # Setup bundle content in a temp structure
        temp_bundle = self.project_root / "temp_bundle"
        temp_bundle.mkdir()
        
        agent_manifest = {
            "name": "new-agent",
            "version": "1.0.0",
            "resources": {"skills": ["skills/test.md"], "scripts": []},
            "dependencies": {}
        }
        with open(temp_bundle / MANIFEST_FILE, "w") as f:
            json.dump(agent_manifest, f)
            
        (temp_bundle / "skills").mkdir()
        (temp_bundle / "skills" / "test.md").write_text("hello")
        
        with zipfile.ZipFile(bundle_path, "w") as zf:
            zf.write(temp_bundle / MANIFEST_FILE, MANIFEST_FILE)
            zf.write(temp_bundle / "skills" / "test.md", "skills/test.md")
            
        # Target path
        target_root = self.agents_dir / "new-agent"
        
        # Perform unpack
        manifest = Librarian.unpack(str(bundle_path), str(target_root))
        
        self.assertTrue(target_root.exists())
        self.assertEqual(manifest["name"], "new-agent")
        
        # Perform Handshake
        Librarian.register_in_project(manifest, str(self.project_root))
        
        with open(self.global_manifest_path) as f:
            global_manifest = json.load(f)
            
        self.assertIn("new-agent", global_manifest["agents"])
        
    # --- #51: _ensure_adapter_wiring ---

    def test_ensure_adapter_wiring_creates_symlinks(self):
        """#51: _ensure_adapter_wiring creates capability symlinks for all adapters."""
        ai_root = self.project_root / ".ai"
        for adapter in ["claude", "gemini", "codex"]:
            (ai_root / "adapters" / adapter).mkdir(parents=True, exist_ok=True)
        (ai_root / "commands").mkdir(parents=True, exist_ok=True)
        (ai_root / "skills").mkdir(parents=True, exist_ok=True)

        Librarian._ensure_adapter_wiring(str(self.project_root))

        claude_commands = ai_root / "adapters" / "claude" / "commands"
        claude_skills   = ai_root / "adapters" / "claude" / "skills"
        gemini_skills   = ai_root / "adapters" / "gemini"  / "skills"
        codex_prompts   = ai_root / "adapters" / "codex"   / "prompts"

        self.assertTrue(claude_commands.is_symlink() or claude_commands.exists())
        self.assertTrue(claude_skills.is_symlink() or claude_skills.exists())
        self.assertTrue(gemini_skills.is_symlink() or gemini_skills.exists())
        self.assertTrue(codex_prompts.is_symlink() or codex_prompts.exists())

    def test_ensure_adapter_wiring_idempotent(self):
        """#51: Calling _ensure_adapter_wiring twice does not raise errors."""
        ai_root = self.project_root / ".ai"
        for adapter in ["claude", "gemini", "codex"]:
            (ai_root / "adapters" / adapter).mkdir(parents=True, exist_ok=True)
        (ai_root / "commands").mkdir(parents=True, exist_ok=True)
        (ai_root / "skills").mkdir(parents=True, exist_ok=True)

        Librarian._ensure_adapter_wiring(str(self.project_root))
        # Second call should be a no-op without raising
        try:
            Librarian._ensure_adapter_wiring(str(self.project_root))
        except Exception as exc:
            self.fail(f"_ensure_adapter_wiring raised on second call: {exc}")


    # --- S1: ZIP Slip ---

    def test_zip_slip_blocked(self):
        """S1: _safe_extract rejects ZIP entries that would escape the target directory."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "extract_here"
            target.mkdir()

            # Build a malicious ZIP with a path-traversal entry
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w") as zf:
                zf.writestr("../escape.txt", "malicious content")
            zip_buf.seek(0)

            with zipfile.ZipFile(zip_buf) as zf:
                with self.assertRaises(ValueError) as ctx:
                    _safe_extract(zf, target)
            self.assertIn("zip slip", str(ctx.exception).lower())

            # The escape file must NOT have been written
            self.assertFalse((Path(tmp) / "escape.txt").exists())

    def test_zip_slip_safe_entries_allowed(self):
        """S1: _safe_extract allows legitimate entries that stay within target."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "extract_here"
            target.mkdir()

            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w") as zf:
                zf.writestr("subdir/file.txt", "safe content")
                zf.writestr("root.txt", "also safe")
            zip_buf.seek(0)

            with zipfile.ZipFile(zip_buf) as zf:
                _safe_extract(zf, target)  # must not raise

            self.assertTrue((target / "subdir" / "file.txt").exists())
            self.assertTrue((target / "root.txt").exists())


class TestFormatSwitchLibrarian(unittest.TestCase):
    """FormatSwitch compilation tests — briefs, wiring, hash-check, migration."""

    def _make_harness(self, root: Path) -> None:
        """Scaffold a minimal harness for tests."""
        ai = root / HARNESS_ROOT
        for d in ["adapters/claude", "adapters/codex", "adapters/gemini",
                  "skills", "commands", "rules", "agents", "memory"]:
            (ai / d).mkdir(parents=True, exist_ok=True)
        # agent-manifest.json so collectors don't crash
        (ai / "agent-manifest.json").write_text(
            '{"factory":"AgentFactory","agents":{}}', encoding="utf-8"
        )

    def _add_skill(self, root: Path, name: str, desc: str = "", triggers: str = "") -> None:
        skill_dir = root / HARNESS_ROOT / "skills" / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        manifest = {"name": name, "description": desc, "triggers": triggers}
        (skill_dir / "skill-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

    # --- compile creates / skips ---

    def test_compile_creates_brief_for_active_adapters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root)
            Librarian._compile_adapter_briefs(str(root))
            for adapter in ["claude", "codex", "gemini"]:
                brief = root / HARNESS_ROOT / "adapters" / adapter / "brief.md"
                self.assertTrue(brief.exists(), f"brief.md missing for {adapter}")

    def test_compile_skips_inactive_adapters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ai = root / HARNESS_ROOT
            # Only create claude adapter dir
            (ai / "adapters" / "claude").mkdir(parents=True, exist_ok=True)
            (ai / "agent-manifest.json").write_text('{"factory":"AF","agents":{}}')
            try:
                Librarian._compile_adapter_briefs(str(root))
            except Exception as exc:
                self.fail(f"_compile_adapter_briefs raised with inactive adapters: {exc}")
            codex_brief = ai / "adapters" / "codex" / "brief.md"
            self.assertFalse(codex_brief.exists())

    # --- format verification ---

    def test_claude_brief_has_skills_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root)
            self._add_skill(root, "my-skill", "A useful skill", "when you need help")
            Librarian._compile_adapter_briefs(str(root))
            brief = (root / HARNESS_ROOT / "adapters" / "claude" / "brief.md").read_text()
            self.assertIn("| Skill |", brief)
            self.assertIn("my-skill", brief)

    def test_codex_brief_has_skills_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root)
            self._add_skill(root, "block-skill", "A block skill", "when coding")
            Librarian._compile_adapter_briefs(str(root))
            brief = (root / HARNESS_ROOT / "adapters" / "codex" / "brief.md").read_text()
            self.assertIn("### block-skill", brief)
            self.assertIn("- Description: A block skill", brief)
            self.assertIn("- Use when: when coding", brief)

    def test_gemini_brief_has_skills_section(self):
        """Gemini brief uses 'Available Skills' after open-standard alignment (2026)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root)
            self._add_skill(root, "tool-skill", "A tool skill", "for analysis")
            Librarian._compile_adapter_briefs(str(root))
            brief = (root / HARNESS_ROOT / "adapters" / "gemini" / "brief.md").read_text()
            self.assertIn("## Available Skills", brief)
            self.assertIn("- Use when:", brief)
            self.assertIn("tool-skill", brief)

    def test_gemini_input_hint_fallback(self):
        """input_hint absent → falls back to triggers field."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root)
            self._add_skill(root, "fallback-skill", "desc", "trigger text")
            Librarian._compile_adapter_briefs(str(root))
            brief = (root / HARNESS_ROOT / "adapters" / "gemini" / "brief.md").read_text()
            self.assertIn("trigger text", brief)

    def test_brief_empty_sections(self):
        """No skills / agents / rules → placeholder text emitted."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root)
            Librarian._compile_adapter_briefs(str(root))
            claude_brief = (root / HARNESS_ROOT / "adapters" / "claude" / "brief.md").read_text()
            self.assertIn("No skills imported yet", claude_brief)
            self.assertIn("No agents registered", claude_brief)

    def test_brief_updates_on_import_skill(self):
        """Adding a skill after first compile appears in all active briefs on re-compile."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root)
            Librarian._compile_adapter_briefs(str(root))
            self._add_skill(root, "late-skill", "Added later")
            Librarian._compile_adapter_briefs(str(root))
            for adapter in ["claude", "codex", "gemini"]:
                brief = (root / HARNESS_ROOT / "adapters" / adapter / "brief.md").read_text()
                self.assertIn("late-skill", brief, f"late-skill missing in {adapter} brief")

    # --- wiring ---

    def test_codex_skills_symlink_created(self):
        """#94: _ensure_adapter_wiring creates codex/skills symlink."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root)
            Librarian._ensure_adapter_wiring(str(root))
            codex_skills = root / HARNESS_ROOT / "adapters" / "codex" / "skills"
            self.assertTrue(codex_skills.is_symlink() or codex_skills.exists())

    def test_adapter_wiring_from_registry(self):
        """Registry-driven wiring creates all expected symlinks."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root)
            Librarian._ensure_adapter_wiring(str(root))
            ai = root / HARNESS_ROOT / "adapters"
            self.assertTrue((ai / "claude" / "skills").is_symlink())
            self.assertTrue((ai / "claude" / "commands").is_symlink())
            self.assertTrue((ai / "gemini" / "skills").is_symlink())
            self.assertTrue((ai / "codex" / "prompts").is_symlink())
            self.assertTrue((ai / "codex" / "skills").is_symlink())

    # --- hash-check ---

    def test_compile_hash_check_skips_unchanged(self):
        """Second compile with no data changes does not rewrite brief.md."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root)
            Librarian._compile_adapter_briefs(str(root))
            brief_path = root / HARNESS_ROOT / "adapters" / "claude" / "brief.md"
            mtime_before = brief_path.stat().st_mtime
            Librarian._compile_adapter_briefs(str(root))
            mtime_after = brief_path.stat().st_mtime
            self.assertEqual(mtime_before, mtime_after, "brief.md was rewritten when content unchanged")

    def test_compile_warning_on_write_failure(self):
        """Read-only brief.md → warning emitted, other adapters still compiled."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root)
            # Pre-create claude brief and make it read-only
            claude_brief = root / HARNESS_ROOT / "adapters" / "claude" / "brief.md"
            claude_brief.write_text("locked", encoding="utf-8")
            claude_brief.chmod(stat.S_IREAD)
            try:
                # Should not raise — warning only, other adapters proceed
                Librarian._compile_adapter_briefs(str(root))
                gemini_brief = root / HARNESS_ROOT / "adapters" / "gemini" / "brief.md"
                self.assertTrue(gemini_brief.exists(), "gemini brief should still compile")
            finally:
                claude_brief.chmod(stat.S_IREAD | stat.S_IWRITE)

    # --- migration ---

    def test_migration_updates_legacy_symlinks(self):
        """Symlinks pointing to AgentFactory.md are migrated to brief.md targets."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root)
            # Compile briefs first so brief.md files exist
            Librarian._compile_adapter_briefs(str(root))
            # Create a legacy CLAUDE.md symlink pointing to AgentFactory.md
            legacy_link = root / "CLAUDE.md"
            legacy_link.symlink_to(f"{HARNESS_ROOT}/AgentFactory.md")
            Librarian._migrate_root_symlinks(str(root))
            self.assertTrue(legacy_link.is_symlink())
            target = os.readlink(str(legacy_link))
            self.assertIn("brief.md", target)
            self.assertNotIn("AgentFactory.md", target)

    def test_migration_skips_custom_symlinks(self):
        """Symlinks not pointing to AgentFactory.md are left untouched."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root)
            Librarian._compile_adapter_briefs(str(root))
            custom_link = root / "CLAUDE.md"
            custom_link.symlink_to("some/custom/target.md")
            Librarian._migrate_root_symlinks(str(root))
            self.assertEqual(os.readlink(str(custom_link)), "some/custom/target.md")

    def test_migration_skips_if_no_brief(self):
        """If brief.md doesn't exist, legacy symlink is not updated (no dangling link)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root)
            # Do NOT compile briefs
            legacy_link = root / "CLAUDE.md"
            legacy_link.symlink_to(f"{HARNESS_ROOT}/AgentFactory.md")
            Librarian._migrate_root_symlinks(str(root))
            # Symlink should still point to AgentFactory.md
            self.assertIn("AgentFactory.md", os.readlink(str(legacy_link)))


    def test_update_harness_files_injects_skills_registry_when_marker_absent(self):
        """update_harness_files appends @skills-registry block to README when marker absent (#121)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root)
            # README without @skills-registry marker
            readme = root / "README.md"
            readme.write_text("# My Project\n\nSome content.\n", encoding="utf-8")
            # Also create required AgentFactory.md
            (root / HARNESS_ROOT / CONTEXT_FILE).write_text(
                "<!-- @agent-registry:start -->\n<!-- @agent-registry:end -->\n"
                "<!-- @skills-registry:start -->\n<!-- @skills-registry:end -->\n",
                encoding="utf-8",
            )
            (root / HARNESS_ROOT / "agent-manifest.json").write_text(
                '{"factory":"AF","agents":{}}', encoding="utf-8"
            )
            self._add_skill(root, "my-skill", "A test skill")
            Librarian.update_harness_files(str(root))
            content = readme.read_text(encoding="utf-8")
            self.assertIn("<!-- @skills-registry:start -->", content)
            self.assertIn("my-skill", content)

    def test_update_harness_files_updates_skills_registry_when_marker_present(self):
        """update_harness_files replaces existing @skills-registry block in README."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root)
            readme = root / "README.md"
            readme.write_text(
                "# My Project\n\n"
                "<!-- @skills-registry:start -->\nold content\n<!-- @skills-registry:end -->\n",
                encoding="utf-8",
            )
            (root / HARNESS_ROOT / CONTEXT_FILE).write_text(
                "<!-- @agent-registry:start -->\n<!-- @agent-registry:end -->\n"
                "<!-- @skills-registry:start -->\n<!-- @skills-registry:end -->\n",
                encoding="utf-8",
            )
            (root / HARNESS_ROOT / "agent-manifest.json").write_text(
                '{"factory":"AF","agents":{}}', encoding="utf-8"
            )
            self._add_skill(root, "updated-skill", "Updated")
            Librarian.update_harness_files(str(root))
            content = readme.read_text(encoding="utf-8")
            self.assertNotIn("old content", content)
            self.assertIn("updated-skill", content)


class TestProjectContextInjection(unittest.TestCase):
    """Tests for preamble extraction + injection into compiled adapter briefs."""

    def _make_harness(self, root: Path, af_content: str | None = None) -> None:
        ai = root / HARNESS_ROOT
        for d in ["adapters/claude", "adapters/codex", "adapters/gemini",
                  "skills", "commands", "rules", "agents", "memory"]:
            (ai / d).mkdir(parents=True, exist_ok=True)
        (ai / "agent-manifest.json").write_text(
            '{"factory":"AgentFactory","agents":{}}', encoding="utf-8"
        )
        if af_content is not None:
            (ai / CONTEXT_FILE).write_text(af_content, encoding="utf-8")

    def test_brief_includes_project_context_from_agentfactory_md(self):
        """Compiled claude brief contains ## Project Context with the preamble text."""
        preamble = "This project does something cool.\n\nMore details here."
        af_content = f"# My Project\n\n{preamble}\n\n<!-- @agent-registry:start -->\n<!-- @agent-registry:end -->\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root, af_content)
            Librarian._compile_adapter_briefs(str(root))
            brief = (root / HARNESS_ROOT / "adapters" / "claude" / "brief.md").read_text(encoding="utf-8")
            self.assertIn("## Project Context", brief)
            self.assertIn("This project does something cool.", brief)

    def test_brief_strips_h1_and_registries_from_project_context(self):
        """H1 title and <!-- @ blocks do not appear inside ## Project Context."""
        af_content = (
            "# AgentFactory\n\n"
            "Project preamble text.\n\n"
            "<!-- @agent-registry:start -->\nsome agent\n<!-- @agent-registry:end -->\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root, af_content)
            Librarian._compile_adapter_briefs(str(root))
            brief = (root / HARNESS_ROOT / "adapters" / "claude" / "brief.md").read_text(encoding="utf-8")
            self.assertIn("Project preamble text.", brief)
            self.assertNotIn("<!-- @agent-registry", brief)
            # H1 title should not appear inside the Project Context section
            ctx_start = brief.find("## Project Context")
            self.assertNotIn("# AgentFactory", brief[ctx_start:ctx_start + 200])

    def test_brief_project_context_absent_when_agentfactory_md_missing(self):
        """No AgentFactory.md → brief compiles without error, no ## Project Context."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root, af_content=None)
            Librarian._compile_adapter_briefs(str(root))
            brief = (root / HARNESS_ROOT / "adapters" / "claude" / "brief.md").read_text(encoding="utf-8")
            self.assertNotIn("## Project Context", brief)

    def test_brief_truncates_preamble_for_tight_budget(self):
        """Codex brief truncates preamble > context_char_limit with warning comment."""
        long_preamble = ("A" * 500 + "\n\n") * 10  # ~5100 chars
        af_content = f"# Title\n\n{long_preamble}\n\n<!-- @agent-registry:start -->\n<!-- @agent-registry:end -->\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root, af_content)
            Librarian._compile_adapter_briefs(str(root))
            brief = (root / HARNESS_ROOT / "adapters" / "codex" / "brief.md").read_text(encoding="utf-8")
            # codex context_char_limit = 2000; preamble is ~5000 chars
            ctx_start = brief.find("## Project Context")
            self.assertGreater(ctx_start, -1)
            ctx_section = brief[ctx_start:]
            self.assertIn("<!-- ⚠ context truncated:", ctx_section)

    def test_brief_no_truncation_when_within_budget(self):
        """Claude brief: preamble <= 4000 chars → no truncation warning."""
        short_preamble = "Short project description.\n\nSecond paragraph."
        af_content = f"# Title\n\n{short_preamble}\n\n<!-- @agent-registry:start -->\n<!-- @agent-registry:end -->\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root, af_content)
            Librarian._compile_adapter_briefs(str(root))
            brief = (root / HARNESS_ROOT / "adapters" / "claude" / "brief.md").read_text(encoding="utf-8")
            self.assertNotIn("context truncated", brief)
            self.assertIn("Short project description.", brief)

    def test_oracle_called_when_key_set_and_truncated(self):
        """Oracle runs when license key is set and preamble is truncated; score printed to stderr."""
        long_preamble = ("B" * 500 + "\n\n") * 10
        af_content = f"# Title\n\n{long_preamble}\n\n<!-- @agent-registry:start -->\n<!-- @agent-registry:end -->\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root, af_content)
            with patch("agent_gen.librarian._run_preamble_oracle", return_value=72) as mock_oracle:
                with patch.dict(os.environ, {"AGENTFACTORY_LICENSE_KEY": "pro_testkey"}):
                    Librarian._compile_adapter_briefs(str(root))
                mock_oracle.assert_called()
                call_args = mock_oracle.call_args
                original, truncated, pr = call_args.args
                self.assertGreater(len(original), len(truncated))
                self.assertEqual(pr, str(root))

    def test_oracle_not_called_without_key(self):
        """Oracle is not invoked when AGENTFACTORY_LICENSE_KEY is absent."""
        long_preamble = ("C" * 500 + "\n\n") * 10
        af_content = f"# Title\n\n{long_preamble}\n\n<!-- @agent-registry:start -->\n<!-- @agent-registry:end -->\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root, af_content)
            env = {k: v for k, v in os.environ.items() if k != "AGENTFACTORY_LICENSE_KEY"}
            with patch("agent_gen.librarian._run_preamble_oracle") as mock_oracle:
                with patch.dict(os.environ, env, clear=True):
                    Librarian._compile_adapter_briefs(str(root))
                mock_oracle.assert_not_called()

    def test_oracle_not_called_when_no_truncation(self):
        """Oracle is not invoked when preamble fits within budget."""
        short_preamble = "Fits easily.\n\nNo truncation needed."
        af_content = f"# Title\n\n{short_preamble}\n\n<!-- @agent-registry:start -->\n<!-- @agent-registry:end -->\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root, af_content)
            with patch("agent_gen.librarian._run_preamble_oracle") as mock_oracle:
                with patch.dict(os.environ, {"AGENTFACTORY_LICENSE_KEY": "pro_testkey"}):
                    Librarian._compile_adapter_briefs(str(root))
                mock_oracle.assert_not_called()

    def test_oracle_error_does_not_crash_compilation(self):
        """If the oracle raises, brief compilation still succeeds."""
        long_preamble = ("D" * 500 + "\n\n") * 10
        af_content = f"# Title\n\n{long_preamble}\n\n<!-- @agent-registry:start -->\n<!-- @agent-registry:end -->\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root, af_content)
            with patch("agent_gen.librarian._run_preamble_oracle", side_effect=Exception("api down")):
                with patch.dict(os.environ, {"AGENTFACTORY_LICENSE_KEY": "pro_testkey"}):
                    Librarian._compile_adapter_briefs(str(root))
            brief = (root / HARNESS_ROOT / "adapters" / "codex" / "brief.md").read_text(encoding="utf-8")
            self.assertIn("context truncated", brief)

    def test_compile_agentfactory_md_adds_rules_and_commands(self):
        """After _compile_adapter_briefs, AgentFactory.md contains rules + commands blocks."""
        af_content = "# My Project\n\nPreamble.\n\n<!-- @agent-registry:start -->\n<!-- @agent-registry:end -->\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root, af_content)
            # Add a rule and command so sections are non-empty
            (root / HARNESS_ROOT / "rules" / "no-secrets.md").write_text(
                "- Never commit secrets.", encoding="utf-8"
            )
            (root / HARNESS_ROOT / "commands" / "git-workflow.md").write_text(
                "<!-- version: 1.0.0 -->\nGit workflow command.", encoding="utf-8"
            )
            Librarian._compile_adapter_briefs(str(root))
            af = (root / HARNESS_ROOT / CONTEXT_FILE).read_text(encoding="utf-8")
            self.assertIn("<!-- @commands-start -->", af)
            self.assertIn("<!-- @commands-end -->", af)
            self.assertIn("<!-- @rules-start -->", af)
            self.assertIn("<!-- @rules-end -->", af)

    def test_harness_identity_references_agentfactory_md(self):
        """_fmt_harness_identity output lists AgentFactory.md in shared context."""
        from agent_gen.librarian import _fmt_harness_identity
        identity = _fmt_harness_identity("claude")
        self.assertIn("AgentFactory.md", identity)
        self.assertIn("project overview", identity)


class TestOpenStandardSkillValidation(unittest.TestCase):
    """Ensure _validate_and_reconcile_skill_manifest accepts open-standard skills.

    The Agent Skills open standard (agentskills.io) only requires name + description.
    version, triggers, and other fields are optional. AgentFactory must not reject
    skills produced by Gemini CLI, Codex, Copilot, or other compliant agents.
    """

    def _make_skill_dir(self, tmp: Path, name: str, frontmatter: str) -> Path:
        skill_dir = tmp / name
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            f"---\n{frontmatter}\n---\n\n# {name}\n",
            encoding="utf-8",
        )
        return skill_dir

    def test_minimal_open_standard_skill_is_accepted(self):
        """name + description only — no version, no triggers."""
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = self._make_skill_dir(
                Path(tmp), "lean-skill",
                "name: lean-skill\ndescription: A minimal open-standard skill"
            )
            # Should not raise
            Librarian._validate_and_reconcile_skill_manifest(skill_dir)
            manifest = json.loads((skill_dir / "skill-manifest.json").read_text())
            self.assertEqual(manifest["name"], "lean-skill")
            self.assertEqual(manifest["description"], "A minimal open-standard skill")
            self.assertNotIn("version", manifest)
            self.assertNotIn("triggers", manifest)

    def test_full_skill_with_optional_fields_is_accepted(self):
        """name + description + version + triggers — full AgentFactory skill."""
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = self._make_skill_dir(
                Path(tmp), "full-skill",
                "name: full-skill\ndescription: Full skill\nversion: 1.2.0\ntriggers: when needed"
            )
            Librarian._validate_and_reconcile_skill_manifest(skill_dir)
            manifest = json.loads((skill_dir / "skill-manifest.json").read_text())
            self.assertEqual(manifest["version"], "1.2.0")
            self.assertEqual(manifest["triggers"], "when needed")

    def test_non_semver_version_is_accepted(self):
        """version field is optional so non-semver strings should not raise."""
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = self._make_skill_dir(
                Path(tmp), "dated-skill",
                "name: dated-skill\ndescription: desc\nversion: 2026-05-18"
            )
            Librarian._validate_and_reconcile_skill_manifest(skill_dir)
            manifest = json.loads((skill_dir / "skill-manifest.json").read_text())
            self.assertEqual(manifest["version"], "2026-05-18")

    def test_missing_name_raises(self):
        """name is still required — raise ValueError if absent."""
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = self._make_skill_dir(
                Path(tmp), "no-name-skill",
                "description: A skill without a name"
            )
            with self.assertRaises(ValueError) as ctx:
                Librarian._validate_and_reconcile_skill_manifest(skill_dir)
            self.assertIn("name", str(ctx.exception))

    def test_missing_description_raises(self):
        """description is still required — raise ValueError if absent."""
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = self._make_skill_dir(
                Path(tmp), "no-desc-skill",
                "name: no-desc-skill"
            )
            with self.assertRaises(ValueError) as ctx:
                Librarian._validate_and_reconcile_skill_manifest(skill_dir)
            self.assertIn("description", str(ctx.exception))

    def test_reconcile_keeps_existing_manifest_name(self):
        """Reconcile path: existing manifest is updated without losing fields."""
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = self._make_skill_dir(
                Path(tmp), "reconcile-skill",
                "name: reconcile-skill\ndescription: Updated desc"
            )
            existing = {"name": "reconcile-skill", "extra_field": "preserved"}
            (skill_dir / "skill-manifest.json").write_text(
                json.dumps(existing), encoding="utf-8"
            )
            Librarian._validate_and_reconcile_skill_manifest(skill_dir)
            manifest = json.loads((skill_dir / "skill-manifest.json").read_text())
            self.assertEqual(manifest["name"], "reconcile-skill")
            self.assertEqual(manifest["description"], "Updated desc")
            self.assertEqual(manifest["extra_field"], "preserved")

    def test_metadata_version_parsed_via_flat_parser(self):
        """metadata.version (open-standard location) is resolved by flat YAML parser."""
        with tempfile.TemporaryDirectory() as tmp:
            skill_md = Path(tmp) / "SKILL.md"
            skill_md.write_text(
                "---\nname: meta-skill\ndescription: desc\nmetadata:\n  version: 3.0.0\n---\n",
                encoding="utf-8",
            )
            version = Librarian._parse_skill_md_version(skill_md)
            self.assertEqual(version, "3.0.0")

    def test_frontmatter_tolerates_leading_whitespace(self):
        """SKILL.md with leading blank lines or spaces before --- is parsed correctly.

        Editors (vim, heredocs) sometimes prepend whitespace. lstrip() absorbs it.
        """
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "ws-skill"
            skill_dir.mkdir()
            # Leading newline + spaces before the opening fence
            (skill_dir / "SKILL.md").write_text(
                "\n  ---\nname: ws-skill\ndescription: Leading whitespace skill\n---\n",
                encoding="utf-8",
            )
            Librarian._validate_and_reconcile_skill_manifest(skill_dir)
            manifest = json.loads((skill_dir / "skill-manifest.json").read_text())
            self.assertEqual(manifest["name"], "ws-skill")
            self.assertEqual(manifest["description"], "Leading whitespace skill")


if __name__ == '__main__':
    unittest.main()
