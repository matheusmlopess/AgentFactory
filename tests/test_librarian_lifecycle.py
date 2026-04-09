import os
import shutil
import json
import unittest
import tempfile
import zipfile
from pathlib import Path

from agent_gen.librarian import Librarian, MANIFEST_FILE

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
        
if __name__ == '__main__':
    unittest.main()