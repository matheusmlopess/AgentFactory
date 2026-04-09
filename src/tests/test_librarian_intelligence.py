import os
import shutil
import json
import unittest
import tempfile
from pathlib import Path
from agent_gen.librarian import Librarian

class TestLibrarianIntelligence(unittest.TestCase):
    def setUp(self):
        """Create a mock agent directory for testing."""
        self.test_dir = tempfile.TemporaryDirectory()
        self.agent_root = Path(self.test_dir.name) / "test-agent"
        self.agent_root.mkdir()
        
        # Create standard directories
        (self.agent_root / "skills").mkdir()
        (self.agent_root / "scripts").mkdir()
        (self.agent_root / "orchestration").mkdir()
        (self.agent_root / "docs").mkdir()
        
        # Create a skill with a manifest
        search_skill = self.agent_root / "skills" / "search"
        search_skill.mkdir()
        with open(search_skill / "skill-manifest.json", "w") as f:
            json.dump({"name": "search", "description": "Search for things."}, f)
        
        # Create a script
        utils_py = self.agent_root / "scripts" / "utils.py"
        utils_py.write_text("def helper(): pass")
        
        # Create a markdown file with dependencies
        skill_md = self.agent_root / "skills" / "search.md"
        skill_md.write_text("<!-- @depends-on: scripts/utils.py -->\n# Search Skill")
        
        # Create a python file with imports
        main_py = self.agent_root / "scripts" / "main.py"
        main_py.write_text("import utils\nprint('hello')")
        
        # Create an orchestration plan
        plan_json = self.agent_root / "orchestration" / "plan.json"
        plan_json.write_text('{"steps": []}')

    def tearDown(self):
        self.test_dir.cleanup()

    def test_librarian_sync_intelligence(self):
        """Test that the Librarian correctly detects intelligence features."""
        librarian = Librarian(str(self.agent_root))
        librarian.init("test-agent")
        manifest = librarian.sync()
        
        # 1. Orchestration plan detection
        self.assertEqual(manifest["orchestration_plan"], "orchestration/plan.json")
        
        # 2. Dependency detection (Markdown)
        self.assertIn("skills/search.md", manifest["dependencies"])
        self.assertIn("scripts/utils.py", manifest["dependencies"]["skills/search.md"])
        
        # 3. Dependency detection (Python imports)
        self.assertIn("scripts/main.py", manifest["dependencies"])
        self.assertIn("scripts/utils.py", manifest["dependencies"]["scripts/main.py"])
        
        # 4. Skill metadata parsing
        self.assertIn("skills/search", manifest["skills_metadata"])
        self.assertEqual(manifest["skills_metadata"]["skills/search"]["name"], "search")

    def test_librarian_audit_intelligence(self):
        """Test that the Librarian audit catches broken dependencies."""
        librarian = Librarian(str(self.agent_root))
        librarian.init("test-agent")
        
        # Sync first to populate manifest
        librarian.sync()
        
        # Manually add a broken dependency to the manifest
        manifest = librarian._load_manifest()
        if "skills/search.md" not in manifest["dependencies"]:
            manifest["dependencies"]["skills/search.md"] = []
        manifest["dependencies"]["skills/search.md"].append("scripts/missing.py")
        librarian._save_manifest(manifest)
        
        report = librarian.audit()
        self.assertIn("skills/search.md -> scripts/missing.py", report["broken_dependencies"])

    def test_librarian_audit_invalid_skill_manifest(self):
        """Test that the Librarian audit catches invalid skill-manifest.json."""
        librarian = Librarian(str(self.agent_root))
        librarian.init("test-agent")
        
        # Create an invalid skill manifest
        invalid_skill = self.agent_root / "skills" / "invalid_skill"
        invalid_skill.mkdir()
        with open(invalid_skill / "skill-manifest.json", "w") as f:
            json.dump({"name": "invalid_skill"}, f) # Missing description
        
        report = librarian.audit()
        self.assertIn("skills/invalid_skill/skill-manifest.json", report["invalid_skill_manifests"])

    def test_librarian_sync_preserves_metadata(self):
        """Test that sync() doesn't overwrite manual metadata."""
        librarian = Librarian(str(self.agent_root))
        librarian.init("test-agent")
        
        # Set manual description
        manifest = librarian._load_manifest()
        manifest["description"] = "Manual Description"
        librarian._save_manifest(manifest)
        
        # Sync
        updated_manifest = librarian.sync()
        self.assertEqual(updated_manifest["description"], "Manual Description")

if __name__ == "__main__":
    unittest.main()
