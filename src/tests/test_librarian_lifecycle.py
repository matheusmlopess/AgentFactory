import io
import json
import os
import stat
import unittest
import tempfile
import zipfile
from pathlib import Path

from agent_gen.librarian import (
    Librarian, MANIFEST_FILE, HARNESS_ROOT, _safe_extract,
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
        gemini_tools    = ai_root / "adapters" / "gemini"  / "tools"
        codex_prompts   = ai_root / "adapters" / "codex"   / "prompts"

        self.assertTrue(claude_commands.is_symlink() or claude_commands.exists())
        self.assertTrue(claude_skills.is_symlink() or claude_skills.exists())
        self.assertTrue(gemini_tools.is_symlink() or gemini_tools.exists())
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

    def test_gemini_brief_has_tools_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_harness(root)
            self._add_skill(root, "tool-skill", "A tool skill", "for analysis")
            Librarian._compile_adapter_briefs(str(root))
            brief = (root / HARNESS_ROOT / "adapters" / "gemini" / "brief.md").read_text()
            self.assertIn("## Available Tools", brief)
            self.assertIn("- Input:", brief)
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
            self.assertTrue((ai / "gemini" / "tools").is_symlink())
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


if __name__ == '__main__':
    unittest.main()
