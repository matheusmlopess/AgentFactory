"""Tests for agentfactory-gen publish and import --from-registry commands."""

import io
import json
import os
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from agent_gen.cli import cli, REGISTRY_URL
from agent_gen.librarian import HARNESS_ROOT, MANIFEST_FILE

AGENTS = f"{HARNESS_ROOT}/agents"


def _setup_agent(runner, name: str, description: str = "A test agent") -> None:
    """Deploy and describe an agent in the current isolated filesystem."""
    runner.invoke(cli, ["deploy", name])
    Path(f"{AGENTS}/{name}/skills/skill.md").touch()
    if description:
        runner.invoke(cli, ["describe", name, "--desc", description])


class TestPublishCommand(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_publish_missing_zip_fails(self):
        """publish should fail with a clear message when the ZIP hasn't been created yet."""
        with self.runner.isolated_filesystem():
            _setup_agent(self.runner, "pub-agent")
            result = self.runner.invoke(cli, ["publish", "pub-agent"])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("pub-agent-v1.0.0.zip", result.output)
            self.assertIn("wrap", result.output)

    def test_publish_missing_description_fails(self):
        """publish should reject a manifest with an empty description."""
        with self.runner.isolated_filesystem():
            runner = self.runner
            runner.invoke(cli, ["deploy", "nodesc-agent"])
            Path(f"{AGENTS}/nodesc-agent/skills/skill.md").touch()
            # Blank the description directly in the manifest file
            mp = Path(f"{AGENTS}/nodesc-agent/agent-manifest.json")
            m = json.loads(mp.read_text())
            m["description"] = ""
            mp.write_text(json.dumps(m))
            runner.invoke(cli, ["wrap", "nodesc-agent"])
            result = runner.invoke(cli, ["publish", "nodesc-agent"])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("description", result.output)

    def test_publish_success(self):
        """publish should POST to registry and print the registry URL."""
        with self.runner.isolated_filesystem():
            _setup_agent(self.runner, "good-agent")
            self.runner.invoke(cli, ["wrap", "good-agent"])

            mock_response = {"slug": "good-agent", "version": "1.0.0"}
            with patch("agent_gen.cli._registry_publish", return_value=mock_response) as mock_pub:
                result = self.runner.invoke(cli, ["publish", "good-agent"])

            self.assertEqual(result.exit_code, 0, result.output)
            mock_pub.assert_called_once()
            call_manifest, call_zip = mock_pub.call_args.args
            self.assertEqual(call_manifest["name"], "good-agent")
            self.assertEqual(call_manifest["description"], "A test agent")
            self.assertIn(REGISTRY_URL, result.output)
            self.assertIn("good-agent@1.0.0", result.output)

    def test_publish_version_override(self):
        """--version flag overrides the manifest version in the ZIP name lookup and upload."""
        with self.runner.isolated_filesystem():
            _setup_agent(self.runner, "ver-agent")
            self.runner.invoke(cli, ["wrap", "ver-agent", "--out", "."])
            # Rename ZIP to match the overridden version
            os.rename("ver-agent-v1.0.0.zip", "ver-agent-v2.0.0.zip")

            with patch("agent_gen.cli._registry_publish", return_value={}) as mock_pub:
                result = self.runner.invoke(cli, ["publish", "ver-agent", "--version", "2.0.0"])

            self.assertEqual(result.exit_code, 0, result.output)
            call_manifest, _ = mock_pub.call_args.args
            self.assertEqual(call_manifest["version"], "2.0.0")

    def test_publish_tags(self):
        """--tag options are forwarded to the registry manifest payload."""
        with self.runner.isolated_filesystem():
            _setup_agent(self.runner, "tagged-agent")
            self.runner.invoke(cli, ["wrap", "tagged-agent"])

            with patch("agent_gen.cli._registry_publish", return_value={}) as mock_pub:
                result = self.runner.invoke(
                    cli, ["publish", "tagged-agent", "--tag", "nlp", "--tag", "retrieval"]
                )

            self.assertEqual(result.exit_code, 0, result.output)
            call_manifest, _ = mock_pub.call_args.args
            self.assertEqual(call_manifest["tags"], ["nlp", "retrieval"])

    def test_publish_quiet_suppresses_output(self):
        """publish in --quiet mode should produce no output on success."""
        with self.runner.isolated_filesystem():
            _setup_agent(self.runner, "quiet-agent")
            self.runner.invoke(cli, ["wrap", "quiet-agent"])

            with patch("agent_gen.cli._registry_publish", return_value={}):
                result = self.runner.invoke(cli, ["--quiet", "publish", "quiet-agent"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(result.output.strip(), "")


class TestImportFromRegistry(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def _make_registry_zip(self, name: str, version: str = "1.0.0") -> bytes:
        """Build a minimal valid agent ZIP in memory."""
        manifest = {
            "name": name,
            "version": version,
            "description": "Registry agent",
            "resources": {"skills": [], "commands": [], "docs": [], "scripts": [], "orchestration": []},
        }
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(MANIFEST_FILE, json.dumps(manifest))
        return buf.getvalue()

    def test_import_from_registry_mocked(self):
        """import --from-registry should download ZIP, unpack, and register the agent."""
        zip_bytes = self._make_registry_zip("reg-agent")
        entry = {
            "name": "reg-agent",
            "version": "1.0.0",
            "zip_url": "https://agentfactory.dev/files/reg-agent-v1.0.0.zip",
        }

        with self.runner.isolated_filesystem():
            with patch("agent_gen.cli._registry_fetch", return_value=(entry, zip_bytes)) as mock_fetch:
                result = self.runner.invoke(cli, ["import", "--from-registry", "reg-agent"])

            self.assertEqual(result.exit_code, 0, result.output)
            mock_fetch.assert_called_once_with("reg-agent")
            self.assertTrue(os.path.exists(f"{AGENTS}/reg-agent/{MANIFEST_FILE}"))

    def test_import_from_registry_versioned_slug(self):
        """import --from-registry my-agent@1.2.0 passes the full slug to _registry_fetch."""
        zip_bytes = self._make_registry_zip("pinned-agent", "1.2.0")
        entry = {
            "name": "pinned-agent",
            "version": "1.2.0",
            "zip_url": "https://agentfactory.dev/files/pinned-agent-v1.2.0.zip",
        }

        with self.runner.isolated_filesystem():
            with patch("agent_gen.cli._registry_fetch", return_value=(entry, zip_bytes)) as mock_fetch:
                result = self.runner.invoke(cli, ["import", "--from-registry", "pinned-agent@1.2.0"])

            self.assertEqual(result.exit_code, 0, result.output)
            mock_fetch.assert_called_once_with("pinned-agent@1.2.0")

    def test_import_mutual_exclusion(self):
        """Mixing --from-registry and --from-git should be rejected."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(
                cli, ["import", "--from-registry", "some-agent", "--from-git", "https://example.com/agent.git"]
            )
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("mutually exclusive", result.output)

    def test_import_no_source_fails(self):
        """import with no source should print a usage error."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(cli, ["import"])
            self.assertNotEqual(result.exit_code, 0)

    def test_import_from_registry_quiet(self):
        """import --from-registry in --quiet mode should produce no output."""
        zip_bytes = self._make_registry_zip("quiet-reg-agent")
        entry = {
            "name": "quiet-reg-agent",
            "version": "1.0.0",
            "zip_url": "https://agentfactory.dev/files/quiet-reg-agent-v1.0.0.zip",
        }

        with self.runner.isolated_filesystem():
            with patch("agent_gen.cli._registry_fetch", return_value=(entry, zip_bytes)):
                result = self.runner.invoke(cli, ["--quiet", "import", "--from-registry", "quiet-reg-agent"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(result.output.strip(), "")
