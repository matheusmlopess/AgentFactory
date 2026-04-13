import shutil
import unittest
import tempfile
from pathlib import Path

from agent_gen.librarian import Librarian

class TestLibrarianRetrofit(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.test_dir.name)
        
        # Mock a legacy "Claude" style agent
        self.legacy_agent = self.project_root / "legacy-agent"
        self.legacy_agent.mkdir()
        
        # Add some legacy structure (canonical Claude)
        claude_dir = self.legacy_agent / ".claude"
        claude_dir.mkdir()
        (claude_dir / "skills").mkdir()
        (claude_dir / "skills" / "test.txt").write_text("prompt")
        (claude_dir / "tools").mkdir()
        (claude_dir / "tools" / "script.py").write_text("print('test')")
        (self.legacy_agent / "CLAUDE.md").write_text("instructions")

    def tearDown(self):
        self.test_dir.cleanup()

    def test_retrofit_success(self):
        librarian = Librarian(str(self.legacy_agent))
        profile, mapping, _ = Librarian.propose_retrofit(str(self.legacy_agent))
        
        self.assertEqual(profile, "claude")
        
        # Execute migration
        librarian.migrate(mapping)
        
        # Check that it converted correctly
        self.assertTrue((self.legacy_agent / "skills" / "test.txt").exists())
        self.assertTrue((self.legacy_agent / "scripts" / "tools" / "script.py").exists())
        self.assertTrue((self.legacy_agent / "docs" / "CLAUDE.md").exists())
        
        # Ensure old directories are gone
        self.assertFalse((self.legacy_agent / ".claude" / "skills").exists())
        self.assertFalse((self.legacy_agent / ".claude" / "tools").exists())

    def test_retrofit_rollback_on_failure(self):
        librarian = Librarian(str(self.legacy_agent))
        profile, mapping, _ = Librarian.propose_retrofit(str(self.legacy_agent))
        
        # Introduce a broken mapping that forces an exception
        # We'll map a non-existent file to an invalid path that raises an OSError
        # Since migrate() only tries to move existing src_paths, we'll need to mock an exception
        # Or we can just mock shutil.move to raise an Exception midway
        
        original_move = shutil.move
        
        def failing_move(src, dst):
            if "tools" in str(src):
                raise OSError("Simulated failure during move")
            return original_move(src, dst)
            
        shutil.move = failing_move
        
        try:
            with self.assertRaises(RuntimeError) as context:
                librarian.migrate(mapping)
            
            self.assertIn("Migration failed and was safely rolled back", str(context.exception))
            
            # The directory should be untouched (no 'skills' or 'docs' created)
            self.assertTrue((self.legacy_agent / ".claude" / "skills").exists())
            self.assertTrue((self.legacy_agent / ".claude" / "tools").exists())
            self.assertTrue((self.legacy_agent / "CLAUDE.md").exists())
            
            # The standard dirs shouldn't exist in the untouched original folder
            self.assertFalse((self.legacy_agent / "skills").exists())
            self.assertFalse((self.legacy_agent / "scripts").exists())
            
        finally:
            shutil.move = original_move

if __name__ == '__main__':
    unittest.main()