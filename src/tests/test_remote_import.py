"""Tests for remote import helpers: _extract_first_paragraph, _extract_source_context,
_auto_init_agent_manifest, _auto_stub_skill_manifests."""

import json
import tempfile
import unittest
from pathlib import Path

from agent_gen.librarian import (
    Librarian,
    _extract_first_paragraph,
)


class TestExtractFirstParagraph(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name, content):
        f = self.root / name
        f.write_text(content)
        return f

    def test_plain_paragraph(self):
        f = self._write("doc.md", "First paragraph here.\nStill same paragraph.")
        result = _extract_first_paragraph(f)
        self.assertIn("First paragraph", result)

    def test_skips_header(self):
        f = self._write("doc.md", "# Title\n\nActual description here.")
        result = _extract_first_paragraph(f)
        self.assertEqual(result, "Actual description here.")

    def test_skips_frontmatter(self):
        f = self._write("doc.md", "---\nname: test\nversion: 1.0\n---\n\n# Head\n\nReal content.")
        result = _extract_first_paragraph(f)
        self.assertEqual(result, "Real content.")

    def test_stops_at_blank_line(self):
        f = self._write("doc.md", "First para.\n\nSecond para.")
        result = _extract_first_paragraph(f)
        self.assertEqual(result, "First para.")

    def test_empty_file(self):
        f = self._write("empty.md", "")
        result = _extract_first_paragraph(f)
        self.assertEqual(result, "")

    def test_truncates_at_200(self):
        f = self._write("long.md", "A" * 300)
        result = _extract_first_paragraph(f)
        self.assertLessEqual(len(result), 200)


class TestExtractSourceContext(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reads_claude_md_description(self):
        (self.repo / "CLAUDE.md").write_text("# Project\n\nThis project does RAG for Claude Code.")
        ctx = Librarian._extract_source_context(str(self.repo))
        self.assertIn("RAG", ctx["description"])

    def test_reads_claude_agents(self):
        agents_dir = self.repo / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "qa-writer.md").write_text("# QA Writer\n\nWrites unit tests for the project.")
        (agents_dir / "security.md").write_text("# Security Auditor\n\nScans for OWASP vulnerabilities.")
        ctx = Librarian._extract_source_context(str(self.repo))
        self.assertIn("qa-writer", ctx["agents"])
        self.assertIn("security", ctx["agents"])
        self.assertIn("unit tests", ctx["agents"]["qa-writer"])
        self.assertIn("OWASP", ctx["agents"]["security"])

    def test_empty_repo(self):
        ctx = Librarian._extract_source_context(str(self.repo))
        self.assertEqual(ctx["description"], "")
        self.assertEqual(ctx["agents"], {})

    def test_fallback_to_agents_md(self):
        (self.repo / "AGENTS.md").write_text("# Agents\n\nThis is the agents manifest.")
        ctx = Librarian._extract_source_context(str(self.repo))
        self.assertIn("agents manifest", ctx["description"])


class TestAutoInitAgentManifest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.agent_dir = Path(self.tmp.name) / "my-agent"
        self.agent_dir.mkdir()
        # Create minimal tracked dirs + one file so sync has something to find
        (self.agent_dir / "docs").mkdir()
        (self.agent_dir / "docs" / "CLAUDE.md").write_text("# Agent\n\nDoes stuff.")
        for d in ["skills", "commands", "scripts", "orchestration"]:
            (self.agent_dir / d).mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_manifest_when_missing(self):
        ctx = {"description": "Local RAG system for Claude Code.", "agents": {}}
        Librarian._auto_init_agent_manifest(str(self.agent_dir), "my-agent", ctx)
        manifest_path = self.agent_dir / "agent-manifest.json"
        self.assertTrue(manifest_path.exists())
        with open(manifest_path) as f:
            data = json.load(f)
        self.assertEqual(data["name"], "my-agent")
        self.assertEqual(data["description"], "Local RAG system for Claude Code.")

    def test_patches_description_on_existing_manifest(self):
        # Pre-create manifest with blank description
        lib = Librarian(str(self.agent_dir))
        lib.init("my-agent")
        ctx = {"description": "Patched description.", "agents": {}}
        Librarian._auto_init_agent_manifest(str(self.agent_dir), "my-agent", ctx)
        with open(self.agent_dir / "agent-manifest.json") as f:
            data = json.load(f)
        self.assertEqual(data["description"], "Patched description.")

    def test_no_description_leaves_existing_unchanged(self):
        lib = Librarian(str(self.agent_dir))
        lib.init("my-agent")
        # Manually set a description
        manifest = lib._load_manifest()
        manifest["description"] = "Original."
        lib._save_manifest(manifest)
        ctx = {"description": "", "agents": {}}
        Librarian._auto_init_agent_manifest(str(self.agent_dir), "my-agent", ctx)
        with open(self.agent_dir / "agent-manifest.json") as f:
            data = json.load(f)
        self.assertEqual(data["description"], "Original.")


class TestAutoStubSkillManifests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.agent_dir = Path(self.tmp.name) / "agent"
        self.agent_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_promotes_flat_agents_and_creates_stubs(self):
        agents_dir = self.agent_dir / "orchestration" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "qa-writer.md").write_text("# QA Writer\n\nWrites tests.")
        (agents_dir / "security.md").write_text("# Security\n\nAudits code.")

        ctx = {
            "description": "",
            "agents": {
                "qa-writer": "Writes comprehensive unit tests.",
                "security": "Scans for OWASP vulnerabilities.",
            }
        }
        Librarian._auto_stub_skill_manifests(str(self.agent_dir), ctx)

        # Each .md should be promoted to its own subdirectory
        self.assertTrue((agents_dir / "qa-writer" / "qa-writer.md").exists())
        self.assertTrue((agents_dir / "security" / "security.md").exists())

        # Each subdirectory should have a skill-manifest.json
        with open(agents_dir / "qa-writer" / "skill-manifest.json") as f:
            sm = json.load(f)
        self.assertEqual(sm["name"], "qa-writer")
        self.assertIn("unit tests", sm["description"])

        with open(agents_dir / "security" / "skill-manifest.json") as f:
            sm = json.load(f)
        self.assertEqual(sm["name"], "security")
        self.assertIn("OWASP", sm["description"])

    def test_skips_existing_skill_manifest(self):
        skills_dir = self.agent_dir / "skills"
        skills_dir.mkdir()
        (skills_dir / "existing.md").write_text("# Existing\n\nAlready set up.")
        existing_skill_dir = skills_dir / "existing"
        existing_skill_dir.mkdir()
        (existing_skill_dir / "existing.md").write_text("# Existing\n\nAlready set up.")
        (existing_skill_dir / "skill-manifest.json").write_text(
            json.dumps({"name": "existing", "version": "2.0.0", "description": "Already here."})
        )

        ctx = {"description": "", "agents": {}}
        Librarian._auto_stub_skill_manifests(str(self.agent_dir), ctx)

        # Version should NOT be overwritten
        with open(existing_skill_dir / "skill-manifest.json") as f:
            sm = json.load(f)
        self.assertEqual(sm["version"], "2.0.0")

    def test_falls_back_to_file_content_for_description(self):
        agents_dir = self.agent_dir / "orchestration" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "documenter.md").write_text("# Documenter\n\nMaintains the devlog automatically.")

        ctx = {"description": "", "agents": {}}  # no pre-extracted description
        Librarian._auto_stub_skill_manifests(str(self.agent_dir), ctx)

        with open(agents_dir / "documenter" / "skill-manifest.json") as f:
            sm = json.load(f)
        self.assertIn("devlog", sm["description"])


if __name__ == "__main__":
    unittest.main()
