import os
import json
import unittest
import tempfile
from pathlib import Path

from agent_gen.librarian import Librarian, MANIFEST_FILE, HARNESS_ROOT, CONTEXT_FILE

class TestGlobalRegistrySync(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.test_dir.name)

        # .ai/ harness structure
        self.ai_root = self.project_root / HARNESS_ROOT
        self.ai_root.mkdir()

        self.agents_dir = self.ai_root / "agents"
        self.agents_dir.mkdir()

        # Global manifest at .ai/agent-manifest.json
        self.global_manifest_path = self.ai_root / MANIFEST_FILE
        self.global_manifest = {
            "factory": "AgentFactory",
            "agents": {
                "test-agent": {
                    "version": "1.0.0",
                    "description": "Old description",
                    "resources": {}
                }
            }
        }
        with open(self.global_manifest_path, "w") as f:
            json.dump(self.global_manifest, f)

        # Single source-of-truth context file
        self.context_file = self.ai_root / CONTEXT_FILE
        self.context_file.write_text(
            "<!-- @agent-registry:start -->\n"
            "- **test-agent**: Old description (See...)\n"
            "<!-- @agent-registry:end -->"
        )

        # Root symlink pointing to .ai/.CLAUDE.md (all CLIs share the same file)
        self.root_agents_md = self.project_root / "AGENTS.md"
        os.symlink(self.context_file, self.root_agents_md)

        # Mock installed agent
        self.agent_dir = self.agents_dir / "test-agent"
        self.agent_dir.mkdir()

        self.agent_manifest = {
            "name": "test-agent",
            "version": "1.0.0",
            "description": "Old description",
            "resources": {"skills": []}
        }
        with open(self.agent_dir / MANIFEST_FILE, "w") as f:
            json.dump(self.agent_manifest, f)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_sync_to_global_updates_harness(self):
        self.agent_manifest["description"] = "New dynamic description"

        Librarian.sync_to_global(self.agent_manifest, str(self.project_root))

        with open(self.global_manifest_path) as f:
            global_data = json.load(f)
        self.assertEqual(global_data["agents"]["test-agent"]["description"], "New dynamic description")

        content = self.context_file.read_text()
        self.assertIn("New dynamic description", content)
        self.assertNotIn("Old description", content)

    def test_update_harness_files_symlink_awareness(self):
        """update_harness_files respects symlinks and doesn't duplicate content."""
        # CLAUDE.md at root symlinks to the same .ai/.CLAUDE.md
        claude_md = self.project_root / "CLAUDE.md"
        os.symlink(self.context_file, claude_md)

        Librarian.update_harness_files(str(self.project_root))

        self.assertTrue(claude_md.is_symlink(), "CLAUDE.md should still be a symlink")

        content = self.context_file.read_text()
        self.assertIn("test-agent", content)

        # Both symlinks resolve to the same file — registry block must appear exactly once
        count = content.count("<!-- @agent-registry:start -->")
        self.assertEqual(count, 1, "Should only have one registry block")

if __name__ == '__main__':
    unittest.main()
