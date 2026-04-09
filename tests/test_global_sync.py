import os
import json
import unittest
import tempfile
from pathlib import Path

from agent_gen.librarian import Librarian, MANIFEST_FILE

class TestGlobalRegistrySync(unittest.TestCase):
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
                "test-agent": {
                    "version": "1.0.0",
                    "description": "Old description",
                    "resources": {}
                }
            }
        }
        with open(self.global_manifest_path, "w") as f:
            json.dump(self.global_manifest, f)
            
        # Mock harness file
        self.core_dir = self.project_root / "core"
        self.core_dir.mkdir(parents=True, exist_ok=True)
        self.agents_md = self.core_dir / "AGENTS.md"
        self.agents_md.write_text("<!-- @agent-registry:start -->\n- **test-agent**: Old description (See...)\n<!-- @agent-registry:end -->")
        
        # Symlink at root
        self.root_agents_md = self.project_root / "AGENTS.md"
        os.symlink(self.agents_md, self.root_agents_md)
        
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
        # We change the local manifest description
        self.agent_manifest["description"] = "New dynamic description"
        
        # Call the sync propagation
        Librarian.sync_to_global(self.agent_manifest, str(self.project_root))
        
        # Verify the global manifest is updated
        with open(self.global_manifest_path) as f:
            global_data = json.load(f)
        self.assertEqual(global_data["agents"]["test-agent"]["description"], "New dynamic description")
        
        # Verify AGENTS.md was dynamically rewritten
        content = self.agents_md.read_text()
        self.assertIn("New dynamic description", content)
        self.assertNotIn("Old description", content)

    def test_update_harness_files_symlink_awareness(self):
        """Test that update_harness_files respects symlinks and doesn't duplicate content."""
        # Setup: create ai/shared/AGENTS.md and symlink CLAUDE.md to it
        shared_dir = self.project_root / "core"
        shared_dir.mkdir(parents=True, exist_ok=True)
        shared_agents_md = shared_dir / "AGENTS.md"
        shared_agents_md.parent.mkdir(exist_ok=True, parents=True)
        shared_agents_md.write_text("# Project Agents\n\n<!-- @agent-registry:start -->\n<!-- @agent-registry:end -->\n")
        
        claude_md = self.project_root / "CLAUDE.md"
        # Create a symlink
        os.symlink(shared_agents_md, claude_md)
        
        # Run update
        Librarian.update_harness_files(str(self.project_root))
        
        # Verify
        self.assertTrue(claude_md.is_symlink(), "CLAUDE.md should still be a symlink")
        
        content = shared_agents_md.read_text()
        self.assertIn("test-agent", content)
        
        # Ensure it wasn't written twice (if the logic wasn't tracking resolved paths)
        count = content.count("<!-- @agent-registry:start -->")
        self.assertEqual(count, 1, "Should only have one registry block")

if __name__ == '__main__':
    unittest.main()