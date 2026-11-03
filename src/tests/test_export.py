"""Tests for `agentfactory-gen export` — patch a local agent back to its source repo."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from agent_gen.cli import cli


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


class TestExport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.runner = CliRunner()

        # 1. a source repo with the agent at agent/
        self.source = self.root / "source"
        (self.source / "agent" / "skills").mkdir(parents=True)
        (self.source / "agent" / "agent-manifest.json").write_text(
            json.dumps({"name": "demo", "version": "1.0.0", "resources": {}})
        )
        (self.source / "agent" / "skills" / "do.md").write_text("OLD\n")
        _git(self.source, "init", "-q")
        _git(self.source, "config", "user.email", "a@a")
        _git(self.source, "config", "user.name", "a")
        _git(self.source, "add", "-A")
        _git(self.source, "commit", "-qm", "init")

        # 2. a bare clone = the pushable "remote"
        self.bare = self.root / "remote.git"
        subprocess.run(
            ["git", "clone", "-q", "--bare", str(self.source), str(self.bare)],
            check=True, capture_output=True,
        )
        self.url = self.bare.as_uri()

        # 3. a project holding a MODIFIED imported agent
        self.proj = self.root / "proj"
        (self.proj / ".ai" / "agents" / "demo" / "skills").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_agent(self, *, source=True):
        agent = self.proj / ".ai" / "agents" / "demo"
        manifest = {"name": "demo", "version": "1.1.0", "resources": {}}
        if source:
            manifest["source"] = {"git": self.url}
        (agent / "agent-manifest.json").write_text(json.dumps(manifest))
        (agent / "skills" / "do.md").write_text("NEW\n")
        (agent / "skills" / "extra.md").write_text("added\n")

    def _branch_tree(self, branch):
        out = self.root / "verify"
        subprocess.run(
            ["git", "clone", "-q", str(self.bare), str(out), "-b", branch],
            check=True, capture_output=True,
        )
        return out

    def test_export_pushes_to_recorded_source(self):
        self._write_agent(source=True)
        res = self.runner.invoke(
            cli, ["export", "demo", "--project-root", str(self.proj), "--no-pr"]
        )
        self.assertEqual(res.exit_code, 0, res.output)
        tree = self._branch_tree("agentfactory/export-demo")
        self.assertEqual((tree / "agent" / "skills" / "do.md").read_text(), "NEW\n")
        self.assertTrue((tree / "agent" / "skills" / "extra.md").exists())
        m = json.loads((tree / "agent" / "agent-manifest.json").read_text())
        self.assertEqual(m["version"], "1.1.0")

    def test_export_explicit_git_url_overrides(self):
        self._write_agent(source=False)  # no recorded source
        res = self.runner.invoke(
            cli, ["export", "demo", "--project-root", str(self.proj),
                  "--git", self.url, "--branch", "x/y", "--no-pr"]
        )
        self.assertEqual(res.exit_code, 0, res.output)
        self.assertTrue((self._branch_tree("x/y") / "agent" / "skills" / "extra.md").exists())

    def test_export_no_source_errors(self):
        self._write_agent(source=False)
        res = self.runner.invoke(cli, ["export", "demo", "--project-root", str(self.proj)])
        self.assertNotEqual(res.exit_code, 0)
        self.assertIn("No source repo", res.output)

    def test_export_no_push_writes_patch(self):
        self._write_agent(source=True)
        res = self.runner.invoke(
            cli, ["export", "demo", "--project-root", str(self.proj), "--no-push"]
        )
        self.assertEqual(res.exit_code, 0, res.output)
        self.assertTrue((self.proj / "demo-export.patch").exists())

    def test_export_missing_agent_errors(self):
        res = self.runner.invoke(cli, ["export", "ghost", "--project-root", str(self.proj)])
        self.assertNotEqual(res.exit_code, 0)
        self.assertIn("not found", res.output)


if __name__ == "__main__":
    unittest.main()
