import os
import shutil
import tempfile
import json
import unittest
from pathlib import Path
from click.testing import CliRunner

from agent_gen.cli import cli
from agent_gen.librarian import MANIFEST_FILE, HARNESS_ROOT

AGENTS = f"{HARNESS_ROOT}/agents"

class TestCliCommands(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_e2e_lifecycle(self):
        with self.runner.isolated_filesystem():
            # Deploy
            result = self.runner.invoke(cli, ["deploy", "test-agent"])
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(os.path.exists(f"{AGENTS}/test-agent/agent-manifest.json"))
            self.assertTrue(os.path.exists(f"{AGENTS}/test-agent/skills"))

            # Create a file so the directory is not empty and gets archived
            Path(f"{AGENTS}/test-agent/skills/my-skill.md").touch()

            # Describe (update description)
            result = self.runner.invoke(cli, ["describe", "test-agent", "--desc", "A test agent"])
            self.assertEqual(result.exit_code, 0)
            with open(f"{AGENTS}/test-agent/agent-manifest.json") as f:
                manifest = json.load(f)
                self.assertEqual(manifest["description"], "A test agent")

            # Wrap
            result = self.runner.invoke(cli, ["wrap", "test-agent"])
            self.assertEqual(result.exit_code, 0)
            zip_path = "test-agent-v1.0.0.zip"
            self.assertTrue(os.path.exists(zip_path))

            # Uninstall
            result = self.runner.invoke(cli, ["uninstall", "test-agent"], input="y\n")
            self.assertEqual(result.exit_code, 0)
            self.assertFalse(os.path.exists(f"{AGENTS}/test-agent"))

            # Import
            result = self.runner.invoke(cli, ["import", zip_path])
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(os.path.exists(f"{AGENTS}/test-agent/agent-manifest.json"))
            self.assertTrue(os.path.exists(f"{AGENTS}/test-agent/skills"))

    def test_retrofit_claude_canonical(self):
        with self.runner.isolated_filesystem():
            mock_path = Path("mock-claude")
            mock_path.mkdir()
            (mock_path / "CLAUDE.md").touch()
            (mock_path / "AGENTS.md").touch()
            claude_dir = mock_path / ".claude"
            for d in ["skills", "commands", "rules", "templates", "tools", "workflows", "agents"]:
                (claude_dir / d).mkdir(parents=True, exist_ok=True)
                (claude_dir / d / ".gitkeep").touch()

            result = self.runner.invoke(cli, ["retrofit", str(mock_path), "--yes"])
            self.assertEqual(result.exit_code, 0)

            self.assertTrue(os.path.exists("mock-claude/agent-manifest.json"))
            self.assertTrue(os.path.exists("mock-claude/skills/.gitkeep"))
            self.assertTrue(os.path.exists("mock-claude/commands/.gitkeep"))
            self.assertTrue(os.path.exists("mock-claude/docs/CLAUDE.md"))
            self.assertTrue(os.path.exists("mock-claude/docs/rules/.gitkeep"))
            self.assertTrue(os.path.exists("mock-claude/scripts/tools/.gitkeep"))
            self.assertTrue(os.path.exists("mock-claude/orchestration/workflows/.gitkeep"))

    def test_retrofit_gemini_canonical(self):
        with self.runner.isolated_filesystem():
            mock_path = Path("mock-gemini")
            mock_path.mkdir()
            (mock_path / "GEMINI.md").touch()
            gemini_dir = mock_path / ".gemini"
            (gemini_dir / "skills").mkdir(parents=True, exist_ok=True)
            (gemini_dir / "skills" / "test.md").touch()

            result = self.runner.invoke(cli, ["retrofit", str(mock_path), "--yes"])
            self.assertEqual(result.exit_code, 0)

            self.assertTrue(os.path.exists("mock-gemini/agent-manifest.json"))
            self.assertTrue(os.path.exists("mock-gemini/docs/GEMINI.md"))
            self.assertTrue(os.path.exists("mock-gemini/skills/test.md"))

    def test_retrofit_codex_canonical(self):
        with self.runner.isolated_filesystem():
            mock_path = Path("mock-codex")
            mock_path.mkdir()
            (mock_path / "codex.md").touch()
            codex_dir = mock_path / ".codex"
            (codex_dir / "prompts").mkdir(parents=True, exist_ok=True)
            (codex_dir / "prompts" / "p1.md").touch()
            (codex_dir / "workflows").mkdir(parents=True, exist_ok=True)
            (codex_dir / "workflows" / "w1.md").touch()

            result = self.runner.invoke(cli, ["retrofit", str(mock_path), "--yes"])
            self.assertEqual(result.exit_code, 0)

            self.assertTrue(os.path.exists("mock-codex/agent-manifest.json"))
            self.assertTrue(os.path.exists("mock-codex/docs/codex.md"))
            self.assertTrue(os.path.exists("mock-codex/skills/prompts/p1.md"))
            self.assertTrue(os.path.exists("mock-codex/orchestration/workflows/w1.md"))

    def test_import_skill_directory(self):
        with self.runner.isolated_filesystem():
            # 1. Setup target agent
            self.runner.invoke(cli, ["deploy", "target-agent"])

            # 2. Setup standalone skill directory
            skill_path = Path("standalone-skill")
            skill_path.mkdir()
            with open(skill_path / "skill-manifest.json", "w") as f:
                json.dump({"name": "super-skill", "version": "1.0.0", "description": "A super skill"}, f)
            (skill_path / "ability.py").write_text("print('skill')")

            # 3. Import skill
            result = self.runner.invoke(cli, ["import-skill", str(skill_path), "--to", "target-agent"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Successfully imported skill 'super-skill'", result.output)

            # 4. Verify
            target_skill_dir = Path(f"{AGENTS}/target-agent/skills/super-skill")
            self.assertTrue(target_skill_dir.exists())
            self.assertTrue((target_skill_dir / "ability.py").exists())

            with open(f"{AGENTS}/target-agent/agent-manifest.json") as f:
                manifest = json.load(f)
                self.assertIn("skills/super-skill", manifest["skills_metadata"])

    def test_import_skill_zip(self):
        with self.runner.isolated_filesystem():
            import zipfile
            # 1. Setup target agent
            self.runner.invoke(cli, ["deploy", "target-agent"])

            # 2. Setup skill and zip it
            skill_path = Path("zip-skill")
            skill_path.mkdir()
            with open(skill_path / "skill-manifest.json", "w") as f:
                json.dump({"name": "zip-skill", "version": "1.0.0", "description": "A zip skill"}, f)
            (skill_path / "logic.py").write_text("pass")

            zip_name = "skill.zip"
            with zipfile.ZipFile(zip_name, 'w') as zf:
                zf.write(skill_path / "skill-manifest.json", "skill-manifest.json")
                zf.write(skill_path / "logic.py", "logic.py")

            # 3. Import skill
            result = self.runner.invoke(cli, ["import-skill", zip_name, "--to", "target-agent"])
            self.assertEqual(result.exit_code, 0)

            # 4. Verify
            target_skill_dir = Path(f"{AGENTS}/target-agent/skills/zip-skill")
            self.assertTrue(target_skill_dir.exists())
            self.assertTrue((target_skill_dir / "logic.py").exists())

if __name__ == '__main__':
    unittest.main()
