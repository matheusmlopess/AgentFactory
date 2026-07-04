import os
import json
import unittest
from pathlib import Path
from click.testing import CliRunner

from agent_gen.cli import cli
from agent_gen.librarian import HARNESS_ROOT

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

    # --- #46: agent-gen init ---

    def test_init_creates_harness(self):
        """#46: agent-gen init scaffolds .ai/ dir tree, milestones.md, and root symlinks."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(cli, ["init"])
            self.assertEqual(result.exit_code, 0)

            # Directory tree
            for subdir in ["adapters/claude", "adapters/gemini", "adapters/codex",
                           "rules", "commands", "skills", "agents", "memory"]:
                self.assertTrue(os.path.isdir(f".ai/{subdir}"), f"missing .ai/{subdir}")

            # Milestone file scaffolded
            self.assertTrue(os.path.exists(".ai/memory/milestones.md"))

            # Source-of-truth file created
            self.assertTrue(os.path.exists(".ai/AgentFactory.md"))

            # Global manifest created
            self.assertTrue(os.path.exists(".ai/agent-manifest.json"))

    def test_init_idempotent(self):
        """#46: Running init twice does not raise errors."""
        with self.runner.isolated_filesystem():
            r1 = self.runner.invoke(cli, ["init"])
            r2 = self.runner.invoke(cli, ["init"])
            self.assertEqual(r1.exit_code, 0)
            self.assertEqual(r2.exit_code, 0)
            self.assertIn("[skip]", r2.output)

    # --- #47: describe --plan ---

    def test_describe_plan_sets_orchestration_plan(self):
        """#47: describe --plan stores orchestration_plan in manifest."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["deploy", "plan-agent"])
            plan_rel = "orchestration/plan.json"
            os.makedirs(f"{AGENTS}/plan-agent/orchestration", exist_ok=True)
            open(f"{AGENTS}/plan-agent/{plan_rel}", "w").close()

            result = self.runner.invoke(cli, ["describe", "plan-agent", "--plan", plan_rel])
            self.assertEqual(result.exit_code, 0)

            with open(f"{AGENTS}/plan-agent/agent-manifest.json") as f:
                manifest = json.load(f)
            self.assertEqual(manifest["orchestration_plan"], plan_rel)

    def test_describe_plan_warns_nonexistent_path(self):
        """#43/#47: describe --plan emits a warning when the path does not exist."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["deploy", "plan-agent"])
            result = self.runner.invoke(cli, ["describe", "plan-agent", "--plan", "orchestration/missing.json"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Warning", result.output)

    # --- #48: wrap --out ---

    def test_wrap_out_option(self):
        """#48: wrap --out <dir> places the zip in the specified directory."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["deploy", "out-agent"])
            Path(f"{AGENTS}/out-agent/skills/demo.md").write_text("hi")

            os.makedirs("archives", exist_ok=True)
            result = self.runner.invoke(cli, ["wrap", "out-agent", "--out", "archives"])
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(os.path.exists("archives/out-agent-v1.0.0.zip"))
            self.assertFalse(os.path.exists("out-agent-v1.0.0.zip"))

    # --- #49: import-skill --to . ---

    def test_import_skill_to_root_project(self):
        """#49: import-skill --to . places skill in .ai/skills/<name>/."""
        with self.runner.isolated_filesystem():
            # Init harness first
            self.runner.invoke(cli, ["init"])

            skill_path = Path("root-skill")
            skill_path.mkdir()
            with open(skill_path / "skill-manifest.json", "w") as f:
                json.dump({"name": "root-skill", "version": "1.0.0", "description": "A root skill"}, f)
            (skill_path / "ability.md").write_text("skill content")

            result = self.runner.invoke(cli, ["import-skill", str(skill_path)])
            self.assertEqual(result.exit_code, 0)

            skill_dir = Path(".ai/skills/root-skill")
            self.assertTrue(skill_dir.exists())
            self.assertTrue((skill_dir / "ability.md").exists())

    # --- #50: import --from-git (mocked subprocess) ---

    def test_import_from_git_invalid_url(self):
        """#50/#58: import --from-git rejects URLs with invalid scheme."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(cli, ["import", "--from-git", "ftp://evil.com/repo"])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("Invalid git URL", result.output)

    def test_import_from_git_valid_url_clones(self):
        """#50: import --from-git with a valid URL triggers git clone."""
        import unittest.mock as mock

        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init"])

            def fake_clone(args, capture_output, text, **kw):
                # Simulate a successful clone by creating the expected directory structure
                cloned_dir = args[-1]
                os.makedirs(cloned_dir, exist_ok=True)
                # Minimal agent scaffold so the pipeline can proceed
                import json as _j
                manifest = {
                    "name": "cloned-agent", "version": "1.0.0",
                    "resources": {"skills": [], "commands": [], "docs": [], "scripts": [], "orchestration": []},
                    "dependencies": {}, "description": "", "git_ref": "abc123",
                }
                with open(os.path.join(cloned_dir, "agent-manifest.json"), "w") as fh:
                    _j.dump(manifest, fh)
                r = mock.MagicMock()
                r.returncode = 0
                return r

            with mock.patch("agent_gen.cli.subprocess.run", side_effect=fake_clone):
                result = self.runner.invoke(
                    cli, ["import", "--from-git", "https://github.com/user/cloned-agent"]
                )
            # Should not fail with URL validation error
            self.assertNotIn("Invalid git URL", result.output)


    # --- Error paths & edge cases ---

    def test_deploy_duplicate_name_fails(self):
        """deploy exits non-zero when agent already exists."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["deploy", "dup-agent"])
            result = self.runner.invoke(cli, ["deploy", "dup-agent"])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("already exists", result.output)

    def test_uninstall_nonexistent_agent_fails(self):
        """uninstall exits non-zero for an agent that doesn't exist."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(cli, ["uninstall", "ghost-agent"])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("not found", result.output)

    def test_uninstall_abort_on_no(self):
        """uninstall aborts cleanly when user declines confirmation."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["deploy", "abort-agent"])
            result = self.runner.invoke(cli, ["uninstall", "abort-agent"], input="n\n")
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Aborted", result.output)
            self.assertTrue(os.path.exists(f"{AGENTS}/abort-agent"))

    def test_audit_clean_agent_passes(self):
        """audit exits 0 and prints clean message for a valid agent."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["deploy", "clean-agent"])
            result = self.runner.invoke(cli, ["audit", "clean-agent"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("clean", result.output)

    def test_audit_broken_resource_fails(self):
        """audit exits 1 and reports broken resource when a tracked file is deleted."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["deploy", "broken-agent"])
            # Write a file, sync it into the manifest, then delete it
            skill_file = Path(f"{AGENTS}/broken-agent/skills/gone.md")
            skill_file.write_text("temporary")
            self.runner.invoke(cli, ["wrap", "broken-agent"])  # sync via wrap
            skill_file.unlink()  # now break it

            result = self.runner.invoke(cli, ["audit", "broken-agent"])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("Broken", result.output)

    def test_import_no_args_fails(self):
        """import with no ZIP_PATH and no --from-git exits with usage error."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(cli, ["import"])
            self.assertNotEqual(result.exit_code, 0)

    def test_import_both_args_fails(self):
        """import with both ZIP_PATH and --from-git exits with usage error."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(cli, ["import", "x.zip", "--from-git", "https://github.com/u/r"])
            self.assertNotEqual(result.exit_code, 0)

    def test_import_missing_zip_fails(self):
        """import with a non-existent zip path exits non-zero."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(cli, ["import", "does-not-exist.zip"])
            self.assertNotEqual(result.exit_code, 0)

    def test_import_agent_already_exists_fails(self):
        """import fails when an agent with the same name already exists."""
        with self.runner.isolated_filesystem():
            # Create, wrap, uninstall, reinstall, then try to import again
            self.runner.invoke(cli, ["deploy", "dupe-import"])
            Path(f"{AGENTS}/dupe-import/skills/x.md").write_text("x")
            self.runner.invoke(cli, ["wrap", "dupe-import"])
            zip_path = "dupe-import-v1.0.0.zip"
            # import once (agent already exists from deploy)
            result = self.runner.invoke(cli, ["import", zip_path])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("already exists", result.output)

    def test_retrofit_path_not_found_fails(self):
        """retrofit exits non-zero for a path that does not exist."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(cli, ["retrofit", "no-such-dir"])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("not found", result.output)

    def test_retrofit_user_abort(self):
        """retrofit aborts cleanly when user declines confirmation."""
        with self.runner.isolated_filesystem():
            path = Path("to-abort")
            path.mkdir()
            (path / "CLAUDE.md").touch()
            result = self.runner.invoke(cli, ["retrofit", "to-abort"], input="n\n")
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Aborted", result.output)

    def test_import_skill_path_not_found_fails(self):
        """import-skill exits non-zero when the given path does not exist."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["deploy", "target"])
            result = self.runner.invoke(cli, ["import-skill", "no-such-skill", "--to", "target"])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("not found", result.output)

    def test_quiet_flag_suppresses_output(self):
        """--quiet / -q suppresses all informational output."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(cli, ["-q", "init"])
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output.strip(), "")

    def test_describe_manifest_missing_fails(self):
        """describe exits non-zero when the agent manifest is not found."""
        with self.runner.isolated_filesystem():
            # Create agent directory without deploying (no manifest)
            os.makedirs(f"{AGENTS}/bare-agent", exist_ok=True)
            result = self.runner.invoke(cli, ["describe", "bare-agent", "--desc", "x"])
            self.assertNotEqual(result.exit_code, 0)

    # --- FormatSwitch CLI tests (#93–#96) ---

    def test_root_symlinks_point_to_briefs(self):
        """After init, CLAUDE.md symlink points to .ai/adapters/claude/brief.md."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(cli, ["init"])
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(os.path.islink("CLAUDE.md"))
            target = os.readlink("CLAUDE.md")
            self.assertIn("brief.md", target)
            self.assertIn("claude", target)

    def test_init_primary_flag_codex(self):
        """--primary codex links all adapter root files; codex files point to codex brief."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(cli, ["init", "--primary", "codex"])
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(os.path.islink("AGENTS.md"))
            agents_target = os.readlink("AGENTS.md")
            self.assertIn("codex", agents_target)
            self.assertIn("brief.md", agents_target)
            self.assertTrue(os.path.islink("CODEX.md"))
            codex_target = os.readlink("CODEX.md")
            self.assertIn("codex", codex_target)
            # All adapter root files are created (all briefs compile on init)
            self.assertTrue(os.path.islink("CLAUDE.md"))
            self.assertIn("claude", os.readlink("CLAUDE.md"))
            self.assertTrue(os.path.islink("GEMINI.md"))
            self.assertIn("gemini", os.readlink("GEMINI.md"))

    def test_adapter_add_creates_dir_and_brief(self):
        """adapter add creates the adapter dir, config, wiring, brief, and root symlinks."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init", "--primary", "claude"])
            # codex was not activated at init (--primary claude)
            result = self.runner.invoke(cli, ["adapter", "add", "codex"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertTrue(os.path.isdir(f"{HARNESS_ROOT}/adapters/codex"))
            self.assertTrue(os.path.exists(f"{HARNESS_ROOT}/adapters/codex/brief.md"))
            self.assertTrue(os.path.islink("AGENTS.md"))
            target = os.readlink("AGENTS.md")
            self.assertIn("codex", target)

    def test_adapter_add_idempotent(self):
        """adapter add can be called twice without overwriting user-edited config."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init", "--primary", "claude"])
            self.runner.invoke(cli, ["adapter", "add", "codex"])
            # Edit the config
            config_path = Path(f"{HARNESS_ROOT}/adapters/codex/config.toml")
            config_path.write_text("[custom]\nmy_key = true\n", encoding="utf-8")
            # Run adapter add again
            result = self.runner.invoke(cli, ["adapter", "add", "codex"])
            self.assertEqual(result.exit_code, 0)
            # Config should not have been overwritten
            self.assertIn("my_key", config_path.read_text())

    def test_adapter_add_unknown_name_errors(self):
        """adapter add with an unknown adapter name raises a usage error."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(cli, ["adapter", "add", "foobar"])
            self.assertNotEqual(result.exit_code, 0)

    def test_adapter_add_symlinks_after_compile(self):
        """Root symlinks are created only after brief.md compiles successfully."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init", "--primary", "claude"])
            result = self.runner.invoke(cli, ["adapter", "add", "gemini"])
            self.assertEqual(result.exit_code, 0)
            brief_path = Path(f"{HARNESS_ROOT}/adapters/gemini/brief.md")
            self.assertTrue(brief_path.exists())
            self.assertTrue(os.path.islink("GEMINI.md"))

    def test_init_creates_all_adapter_root_symlinks(self):
        """init with default --primary claude creates root symlinks for all adapters (#120)."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(cli, ["init"])
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(os.path.islink("CLAUDE.md"))
            self.assertIn("claude", os.readlink("CLAUDE.md"))
            self.assertTrue(os.path.islink("AGENTS.md"))
            self.assertIn("codex", os.readlink("AGENTS.md"))
            self.assertTrue(os.path.islink("CODEX.md"))
            self.assertIn("codex", os.readlink("CODEX.md"))
            self.assertTrue(os.path.islink("GEMINI.md"))
            self.assertIn("gemini", os.readlink("GEMINI.md"))

    def test_adapter_add_skips_non_symlink_root_file(self):
        """adapter add does not clobber an existing regular-file AGENTS.md."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init", "--primary", "claude"])
            # Replace the symlink created by init with a real file
            if os.path.islink("AGENTS.md"):
                os.unlink("AGENTS.md")
            Path("AGENTS.md").write_text("# Custom content\n")
            result = self.runner.invoke(cli, ["adapter", "add", "codex"])
            self.assertEqual(result.exit_code, 0)
            # File should still exist and not be a symlink
            self.assertFalse(os.path.islink("AGENTS.md"))
            self.assertIn("Custom content", Path("AGENTS.md").read_text())

    def test_adapter_add_ok_message_when_skills_within_budget(self):
        """adapter add prints ok message when no skills exceed the adapter's char limit."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init", "--primary", "claude"])
            result = self.runner.invoke(cli, ["adapter", "add", "codex"])
            self.assertEqual(result.exit_code, 0, result.output)
            # No skills are imported yet — all-clear message should appear
            self.assertIn("ok", result.output.lower())

    def test_adapter_add_warns_when_skill_over_budget(self):
        """adapter add emits a warning when a SKILL.md exceeds the adapter's char limit."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init", "--primary", "claude"])
            # Create a skill that exceeds the codex char limit (10,000 bytes)
            skill_dir = Path(f"{HARNESS_ROOT}/skills/big-skill")
            skill_dir.mkdir(parents=True)
            oversized = "x" * 11_000
            (skill_dir / "SKILL.md").write_text(
                f"---\nname: big-skill\ndescription: test\n---\n{oversized}\n"
            )
            result = self.runner.invoke(cli, ["adapter", "add", "codex"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("exceed", result.output)
            self.assertIn("big-skill", result.output)

    def test_adapter_add_check_completeness_missing_script_warns(self):
        """--check-completeness when script is absent prints a warning and exits 0."""
        with self.runner.isolated_filesystem():
            # init without creating the completeness script
            self.runner.invoke(cli, ["init", "--primary", "claude"])
            skill_dir = Path(f"{HARNESS_ROOT}/skills/big-skill")
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: big-skill\ndescription: test\n---\n" + "x" * 11_000
            )
            result = self.runner.invoke(
                cli, ["adapter", "add", "codex", "--check-completeness"]
            )
            self.assertEqual(result.exit_code, 0, result.output)
            # Script is not present in isolated filesystem → script-not-found warning
            self.assertIn("completeness script not found", result.output)

    def test_adapter_add_reads_threshold_from_config(self):
        """adapter-add uses per-adapter threshold from .ai/config/completeness.json."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init", "--primary", "claude"])
            # Write a completeness config with a tight codex threshold
            config_dir = Path(f"{HARNESS_ROOT}/config")
            config_dir.mkdir(parents=True)
            (config_dir / "completeness.json").write_text(
                '{"completeness": {"thresholds": {"codex": 99}, "default": 80}}'
            )
            # Over-budget skill for codex (10k limit)
            skill_dir = Path(f"{HARNESS_ROOT}/skills/big-skill")
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("---\nname: big-skill\ndescription: t\n---\n" + "x" * 11_000)
            result = self.runner.invoke(cli, ["adapter", "add", "codex"])
            self.assertEqual(result.exit_code, 0, result.output)
            # The warning should mention threshold 99
            self.assertIn("99", result.output)

    def test_adapter_add_falls_back_to_default_threshold(self):
        """adapter-add uses 'default' threshold when adapter is not listed in config."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init", "--primary", "claude"])
            config_dir = Path(f"{HARNESS_ROOT}/config")
            config_dir.mkdir(parents=True)
            # No 'claude' key — should fall back to default 85
            (config_dir / "completeness.json").write_text(
                '{"completeness": {"thresholds": {}, "default": 85}}'
            )
            skill_dir = Path(f"{HARNESS_ROOT}/skills/big-skill")
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("---\nname: big-skill\ndescription: t\n---\n" + "x" * 19_000)
            result = self.runner.invoke(cli, ["adapter", "add", "claude"])
            self.assertEqual(result.exit_code, 0, result.output)
            # Falls back to default 85 from config
            self.assertIn("85", result.output)

    def test_brief_cmd_regenerates_all(self):
        """brief command updates AgentFactory.md and all active adapter briefs."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init"])
            result = self.runner.invoke(cli, ["brief"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("brief.md", result.output)
            self.assertIn("ok", result.output)

    def test_brief_contains_harness_identity_block(self):
        """Every compiled brief contains the universal harness identity block."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init", "--primary", "claude"])
            brief = Path(f"{HARNESS_ROOT}/adapters/claude/brief.md")
            content = brief.read_text()
            # Block header present
            self.assertIn("## Harness", content)
            # Self-reference marker
            self.assertIn("YOU ARE HERE", content)
            # Cross-adapter references for all registry adapters
            self.assertIn("codex", content)
            self.assertIn("gemini", content)
            # Key harness paths present
            self.assertIn("agent-manifest.json", content)
            self.assertIn("milestones.md", content)
            self.assertIn("agentfactory-gen brief", content)

    def test_harness_identity_you_are_here_per_adapter(self):
        """The YOU ARE HERE marker points to the correct adapter in each brief."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init", "--primary", "claude"])
            self.runner.invoke(cli, ["adapter", "add", "codex"])
            claude_brief = Path(f"{HARNESS_ROOT}/adapters/claude/brief.md").read_text()
            codex_brief  = Path(f"{HARNESS_ROOT}/adapters/codex/brief.md").read_text()
            self.assertIn("claude", claude_brief.split("YOU ARE HERE")[0].split("\n")[-1])
            self.assertIn("codex",  codex_brief.split("YOU ARE HERE")[0].split("\n")[-1])

    def test_brief_cmd_no_harness_errors(self):
        """brief command exits non-zero when there is no .ai/ harness."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(cli, ["brief"])
            self.assertNotEqual(result.exit_code, 0)

    def test_migration_updates_legacy_symlinks_via_init(self):
        """Calling init twice after update migrates old AgentFactory.md symlinks."""
        with self.runner.isolated_filesystem():
            # Simulate legacy: CLAUDE.md → .ai/AgentFactory.md
            os.makedirs(f"{HARNESS_ROOT}/adapters/claude", exist_ok=True)
            os.makedirs(f"{HARNESS_ROOT}/adapters/codex", exist_ok=True)
            os.makedirs(f"{HARNESS_ROOT}/adapters/gemini", exist_ok=True)
            os.makedirs(f"{HARNESS_ROOT}/skills", exist_ok=True)
            os.makedirs(f"{HARNESS_ROOT}/commands", exist_ok=True)
            os.makedirs(f"{HARNESS_ROOT}/rules", exist_ok=True)
            os.makedirs(f"{HARNESS_ROOT}/agents", exist_ok=True)
            os.makedirs(f"{HARNESS_ROOT}/memory", exist_ok=True)
            Path(f"{HARNESS_ROOT}/AgentFactory.md").write_text("# Context\n")
            Path(f"{HARNESS_ROOT}/agent-manifest.json").write_text('{"factory":"AF","agents":{}}')
            os.symlink(f"{HARNESS_ROOT}/AgentFactory.md", "CLAUDE.md")
            # Run brief to trigger migration
            from agent_gen.librarian import Librarian
            Librarian.update_harness_files(".")
            target = os.readlink("CLAUDE.md")
            self.assertIn("brief.md", target)

    def test_migration_skips_if_no_brief(self):
        """Migration does not create a dangling symlink when brief.md doesn't exist."""
        with self.runner.isolated_filesystem():
            os.makedirs(f"{HARNESS_ROOT}/adapters/claude", exist_ok=True)
            Path(f"{HARNESS_ROOT}/AgentFactory.md").write_text("# Context\n")
            os.symlink(f"{HARNESS_ROOT}/AgentFactory.md", "CLAUDE.md")
            from agent_gen.librarian import Librarian
            Librarian._migrate_root_symlinks(".")
            # Brief doesn't exist → symlink unchanged
            self.assertIn("AgentFactory.md", os.readlink("CLAUDE.md"))


class TestWave1Fixes(unittest.TestCase):
    """Wave 1 foundation-bug regression tests (#132–#136)."""

    def setUp(self):
        self.runner = CliRunner()

    # --- #133: --version flag ---

    def test_version_flag_exits_zero(self):
        """--version exits 0 and prints a version string."""
        result = self.runner.invoke(cli, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertRegex(result.output, r"\d+\.\d+")

    # --- #132: audit treats untracked files as warnings ---

    def test_audit_untracked_files_exits_zero(self):
        """audit exits 0 when files exist on disk but are not yet in the manifest."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["deploy", "untrack-agent"])
            # Add a file without syncing — it becomes 'untracked'
            Path(f"{AGENTS}/untrack-agent/docs/extra.md").write_text("# extra\n<!-- version: 1.0.0 -->")
            result = self.runner.invoke(cli, ["audit", "untrack-agent"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Untracked", result.output)

    def test_audit_broken_resource_still_fatal(self):
        """audit still exits 1 for broken resources even after the #132 fix."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["deploy", "broken2"])
            skill_file = Path(f"{AGENTS}/broken2/skills/gone.md")
            skill_file.write_text("gone")
            self.runner.invoke(cli, ["wrap", "broken2"])
            skill_file.unlink()
            result = self.runner.invoke(cli, ["audit", "broken2"])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("Broken", result.output)

    # --- #136: wrap --print-path ---

    def test_wrap_print_path_outputs_zip_path(self):
        """wrap --print-path prints only the archive path to stdout."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["deploy", "printpath-agent"])
            Path(f"{AGENTS}/printpath-agent/skills/s.md").write_text("# s\n<!-- version: 1.0.0 -->")
            result = self.runner.invoke(cli, ["wrap", "printpath-agent", "--print-path"])
            self.assertEqual(result.exit_code, 0, result.output)
            lines = [ln for ln in result.output.strip().splitlines() if ln.strip()]
            last_line = lines[-1]
            self.assertTrue(last_line.endswith(".zip"), f"Expected .zip path, got: {last_line!r}")

    def test_wrap_print_path_with_quiet_still_outputs_path(self):
        """--print-path emits the path even when --quiet is set."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["deploy", "q-agent"])
            Path(f"{AGENTS}/q-agent/skills/s.md").write_text("# s\n<!-- version: 1.0.0 -->")
            result = self.runner.invoke(cli, ["-q", "wrap", "q-agent", "--print-path"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn(".zip", result.output)

    # --- #135: import --project-root conflict check ---

    def test_import_project_root_conflict_detected(self):
        """import --project-root detects agent conflict in the target, not CWD."""
        with self.runner.isolated_filesystem():
            import shutil

            # Build a minimal agent ZIP
            self.runner.invoke(cli, ["deploy", "conflict-agent"])
            Path(f"{AGENTS}/conflict-agent/skills/s.md").write_text("x")
            self.runner.invoke(cli, ["wrap", "conflict-agent"])
            zip_name = "conflict-agent-v1.0.0.zip"
            self.assertTrue(Path(zip_name).exists())

            # Set up a separate project dir that already has conflict-agent deployed
            target = Path("target-project")
            target.mkdir()
            self.runner.invoke(cli, ["--quiet", "init", "--project-root", str(target)])
            self.runner.invoke(cli, ["deploy", "conflict-agent"])
            # move the agent into target
            src = Path(f"{AGENTS}/conflict-agent")
            dst = target / HARNESS_ROOT / "agents" / "conflict-agent"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(str(src), str(dst))

            # Importing into target-project should fail because the agent already exists there
            result = self.runner.invoke(
                cli, ["import", zip_name, "--project-root", str(target)]
            )
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("already exists", result.output)

    # --- #134: import-skill parses SKILL.md frontmatter ---

    def _make_skill_dir(self, base: Path, name: str, *, triggers: str = "test trigger") -> Path:
        """Helper: create a minimal skill directory with SKILL.md frontmatter."""
        skill_dir = base / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\nversion: 1.0.0\ndescription: Test skill\ntriggers: {triggers}\n---\n\n# {name}\n"
        )
        return skill_dir

    def test_import_skill_writes_triggers_to_manifest(self):
        """import-skill writes triggers from SKILL.md frontmatter to skill-manifest.json."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init"])
            self.runner.invoke(cli, ["deploy", "target-agent"])
            skill_dir = self._make_skill_dir(Path("."), "my-skill", triggers="invoke me, trigger me")
            result = self.runner.invoke(cli, ["import-skill", str(skill_dir), "--to", "target-agent"])
            self.assertEqual(result.exit_code, 0, result.output)
            manifest_path = Path(f"{AGENTS}/target-agent/skills/my-skill/skill-manifest.json")
            self.assertTrue(manifest_path.exists())
            data = json.loads(manifest_path.read_text())
            self.assertEqual(data["triggers"], "invoke me, trigger me")

    def test_import_skill_root_writes_triggers(self):
        """import-skill --to . (root) also reconciles SKILL.md frontmatter."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init"])
            skill_dir = self._make_skill_dir(Path("."), "root-skill", triggers="root trigger")
            result = self.runner.invoke(cli, ["import-skill", str(skill_dir)])
            self.assertEqual(result.exit_code, 0, result.output)
            manifest_path = Path(f"{HARNESS_ROOT}/skills/root-skill/skill-manifest.json")
            data = json.loads(manifest_path.read_text())
            self.assertEqual(data["triggers"], "root trigger")

    def test_import_skill_missing_frontmatter_fields_fails(self):
        """import-skill exits non-zero when SKILL.md is missing required fields.

        Open standard requires name + description. version and triggers are optional.
        """
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["deploy", "validate-agent"])
            skill_dir = Path("bad-skill")
            skill_dir.mkdir()
            # description field is missing — still required by the open standard
            (skill_dir / "SKILL.md").write_text(
                "---\nname: bad-skill\nversion: 1.0.0\n---\n"
            )
            result = self.runner.invoke(
                cli, ["import-skill", str(skill_dir), "--to", "validate-agent"]
            )
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("description", result.output.lower())

    def test_import_skill_open_standard_minimal_succeeds(self):
        """import-skill accepts open-standard skills with only name + description."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["deploy", "validate-agent"])
            skill_dir = Path("open-skill")
            skill_dir.mkdir()
            # Open-standard minimal: name + description only, no version, no triggers
            (skill_dir / "SKILL.md").write_text(
                "---\nname: open-skill\ndescription: A cross-agent open-standard skill\n---\n"
            )
            result = self.runner.invoke(
                cli, ["import-skill", str(skill_dir), "--to", "validate-agent"]
            )
            self.assertEqual(result.exit_code, 0, result.output)


class TestWave2Security(unittest.TestCase):
    """Wave 2 security regression tests (#142, #143, #144, #146)."""

    def setUp(self):
        self.runner = CliRunner()

    def _make_agent_zip(self, runner, name="sec-agent", with_scripts=False) -> Path:
        """Helper: deploy + optionally add scripts + wrap → return zip path."""
        runner.invoke(cli, ["deploy", name])
        Path(f"{AGENTS}/{name}/docs/readme.md").write_text("# hi")
        if with_scripts:
            Path(f"{AGENTS}/{name}/scripts/setup.sh").write_text("#!/bin/bash\necho hi")
        runner.invoke(cli, ["wrap", name])
        return Path(f"{name}-v1.0.0.zip")

    # --- #146: atomic manifest writes ---

    def test_save_manifest_atomic_tmp_absent_after_success(self):
        """After a successful save, no .tmp file should remain next to the manifest."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["deploy", "atomic-agent"])
            manifest_path = Path(f"{AGENTS}/atomic-agent/agent-manifest.json")
            tmp_path = manifest_path.with_suffix(".json.tmp")
            self.assertFalse(tmp_path.exists(), ".tmp file must not persist after save")

    # --- #146: dry-run mode ---

    def test_import_dry_run_writes_nothing(self):
        """--dry-run prints a preview and leaves the project directory untouched."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init"])
            zip_path = self._make_agent_zip(self.runner, "dr-agent")
            # Uninstall the deployed agent so the zip is the only copy
            self.runner.invoke(cli, ["uninstall", "dr-agent"], input="y\n")

            result = self.runner.invoke(cli, ["import", str(zip_path), "--dry-run"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("DRY RUN", result.output)
            self.assertIn("dr-agent", result.output)
            # Agent must NOT be registered
            self.assertFalse(Path(f"{AGENTS}/dr-agent").exists())

    def test_import_dry_run_shows_conflict(self):
        """--dry-run reports a conflict when the agent already exists."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init"])
            zip_path = self._make_agent_zip(self.runner, "conflict-dr")
            # Agent still exists (not uninstalled) → conflict
            result = self.runner.invoke(cli, ["import", str(zip_path), "--dry-run"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("conflict", result.output.lower())

    # --- #142: scripts review gate ---

    def test_import_scripts_prompts_user(self):
        """import with scripts/ present prompts the user before proceeding."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init"])
            zip_path = self._make_agent_zip(self.runner, "script-agent", with_scripts=True)
            self.runner.invoke(cli, ["uninstall", "script-agent"], input="y\n")

            # Answer 'n' — import should be cancelled
            result = self.runner.invoke(
                cli, ["import", str(zip_path)], input="n\n"
            )
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("cancelled", result.output.lower())
            self.assertFalse(Path(f"{AGENTS}/script-agent").exists())

    def test_import_allow_scripts_skips_prompt(self):
        """--allow-scripts bypasses the interactive scripts gate."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init"])
            zip_path = self._make_agent_zip(self.runner, "skip-script-agent", with_scripts=True)
            self.runner.invoke(cli, ["uninstall", "skip-script-agent"], input="y\n")

            result = self.runner.invoke(
                cli, ["import", str(zip_path), "--allow-scripts"]
            )
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertTrue(Path(f"{AGENTS}/skip-script-agent").exists())

    def test_import_no_scripts_no_prompt(self):
        """import without scripts/ does not prompt the user."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init"])
            zip_path = self._make_agent_zip(self.runner, "clean-import-agent")
            self.runner.invoke(cli, ["uninstall", "clean-import-agent"], input="y\n")

            result = self.runner.invoke(cli, ["import", str(zip_path)])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertNotIn("executable script", result.output.lower())

    # --- #144: checksum verification ---

    def test_wrap_emits_sha256_sidecar(self):
        """wrap produces a .sha256 sidecar alongside the ZIP."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["deploy", "hash-agent"])
            Path(f"{AGENTS}/hash-agent/docs/r.md").write_text("x")
            self.runner.invoke(cli, ["wrap", "hash-agent"])
            sidecar = Path("hash-agent-v1.0.0.zip.sha256")
            self.assertTrue(sidecar.exists(), "SHA-256 sidecar not produced")
            content = sidecar.read_text()
            self.assertRegex(content, r"^[0-9a-f]{64}\s")

    def test_import_checksum_valid_passes(self):
        """import --checksum accepts the ZIP when the hash matches."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init"])
            zip_path = self._make_agent_zip(self.runner, "check-agent")
            sidecar = Path("check-agent-v1.0.0.zip.sha256")
            self.runner.invoke(cli, ["uninstall", "check-agent"], input="y\n")

            result = self.runner.invoke(
                cli, ["import", str(zip_path), "--checksum", str(sidecar)]
            )
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("verified", result.output.lower())

    def test_import_checksum_mismatch_fails(self):
        """import --checksum exits 1 when the ZIP hash does not match the sidecar."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init"])
            zip_path = self._make_agent_zip(self.runner, "tamper-agent")
            sidecar = Path("tamper-agent-v1.0.0.zip.sha256")
            # Tamper the ZIP
            zip_path.write_bytes(b"garbage" + zip_path.read_bytes())
            self.runner.invoke(cli, ["uninstall", "tamper-agent"], input="y\n")

            result = self.runner.invoke(
                cli, ["import", str(zip_path), "--checksum", str(sidecar)]
            )
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("mismatch", result.output.lower())

    # --- #143: --project-root validation ---

    def test_import_invalid_project_root_fails(self):
        """import --project-root to a non-harness directory exits non-zero."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init"])
            zip_path = self._make_agent_zip(self.runner, "root-check-agent")
            self.runner.invoke(cli, ["uninstall", "root-check-agent"], input="y\n")
            # Point to a dir with no .ai/
            bad_root = Path("not-a-project")
            bad_root.mkdir()
            result = self.runner.invoke(
                cli, ["import", str(zip_path), "--project-root", str(bad_root)]
            )
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("not an AgentFactory project", result.output)

    def test_import_default_project_root_skips_validation(self):
        """import with default --project-root '.' does not require pre-validated .ai/."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init"])
            zip_path = self._make_agent_zip(self.runner, "default-root-agent")
            self.runner.invoke(cli, ["uninstall", "default-root-agent"], input="y\n")
            result = self.runner.invoke(cli, ["import", str(zip_path)])
            self.assertEqual(result.exit_code, 0, result.output)


class TestGapMitigations(unittest.TestCase):
    """Gap mitigation tests — Wave 1 + Wave 2 post-analysis items."""

    def setUp(self):
        self.runner = CliRunner()

    def _make_agent_zip(self, runner, name="gap-agent", with_scripts=False,
                        with_shebang_cmd=False) -> Path:
        runner.invoke(cli, ["deploy", name])
        Path(f"{AGENTS}/{name}/docs/readme.md").write_text("# hi")
        if with_scripts:
            Path(f"{AGENTS}/{name}/scripts/setup.sh").write_text("#!/bin/bash\necho hi")
        if with_shebang_cmd:
            Path(f"{AGENTS}/{name}/commands/evil.sh").write_text("#!/bin/bash\nrm -rf /")
        runner.invoke(cli, ["wrap", name])
        return Path(f"{name}-v1.0.0.zip")

    # --- audit --fix (#Wave1-gap) ---

    def test_audit_fix_resolves_untracked_files(self):
        """audit --fix syncs untracked files into the manifest and exits 0."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["deploy", "fix-agent"])
            # Add a file without syncing → untracked
            Path(f"{AGENTS}/fix-agent/skills/new.md").write_text("new skill")

            # Without --fix, untracked is a warning (#132): exit 0, not clean
            r = self.runner.invoke(cli, ["audit", "fix-agent"])
            self.assertEqual(r.exit_code, 0, r.output)
            self.assertIn("Untracked", r.output)
            self.assertNotIn("clean", r.output.lower())

            # With --fix, sync resolves it → exit 0
            r = self.runner.invoke(cli, ["audit", "fix-agent", "--fix"])
            self.assertEqual(r.exit_code, 0, r.output)
            self.assertIn("clean", r.output.lower())

    def test_audit_fix_does_not_hide_broken_resources(self):
        """audit --fix still exits 1 when broken (missing) resources are present."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["deploy", "fix-broken"])
            skill_file = Path(f"{AGENTS}/fix-broken/skills/gone.md")
            skill_file.write_text("temp")
            self.runner.invoke(cli, ["wrap", "fix-broken"])
            skill_file.unlink()

            r = self.runner.invoke(cli, ["audit", "fix-broken", "--fix"])
            self.assertNotEqual(r.exit_code, 0)
            self.assertIn("Broken", r.output)

    # --- import-skill --project-root (#Wave1-gap) ---

    def test_import_skill_project_root_explicit(self):
        """import-skill --project-root places skill in the specified root's .ai/skills/."""
        with self.runner.isolated_filesystem():
            # Init two side-by-side project roots
            import os
            os.makedirs("proj-a")
            self.runner.invoke(cli, ["init", "--project-root", "proj-a"])

            skill_path = Path("my-skill")
            skill_path.mkdir()
            import json as _j
            with open(skill_path / "skill-manifest.json", "w") as f:
                _j.dump({"name": "my-skill", "version": "1.0.0", "description": "test"}, f)
            (skill_path / "logic.md").write_text("content")

            result = self.runner.invoke(
                cli, ["import-skill", str(skill_path), "--project-root", "proj-a"]
            )
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertTrue(Path("proj-a/.ai/skills/my-skill/logic.md").exists())

    def test_import_skill_invalid_project_root_fails(self):
        """import-skill --project-root to a non-harness dir exits non-zero."""
        with self.runner.isolated_filesystem():
            import os
            os.makedirs("not-a-project")
            skill_path = Path("dummy-skill")
            skill_path.mkdir()
            import json as _j
            with open(skill_path / "skill-manifest.json", "w") as f:
                _j.dump({"name": "dummy", "version": "1.0.0", "description": "d"}, f)

            result = self.runner.invoke(
                cli, ["import-skill", str(skill_path), "--project-root", "not-a-project"]
            )
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("not an AgentFactory project", result.output)

    # --- brief / adapter add use shared _assert_valid_project_root (#Wave2-gap) ---

    def test_brief_invalid_project_root_error_message(self):
        """brief with no harness emits the shared 'not an AgentFactory project' message."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(cli, ["brief"])
            self.assertNotEqual(result.exit_code, 0)
            # Message comes from _assert_valid_project_root, not a one-off inline check
            self.assertIn("not an AgentFactory project", result.output)

    def test_adapter_add_invalid_project_root_error_message(self):
        """adapter add with no harness emits the shared 'not an AgentFactory project' message."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(cli, ["adapter", "add", "gemini"])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("not an AgentFactory project", result.output)

    # --- shebang detection in commands/ and orchestration/ (#Wave2-gap) ---

    def test_import_shebang_in_commands_triggers_gate(self):
        """import prompts when commands/ contains a file with a shebang line."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init"])
            zip_path = self._make_agent_zip(
                self.runner, "shebang-cmd-agent", with_shebang_cmd=True
            )
            self.runner.invoke(cli, ["uninstall", "shebang-cmd-agent"], input="y\n")

            # Answer 'n' — import should be cancelled
            result = self.runner.invoke(cli, ["import", str(zip_path)], input="n\n")
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("cancelled", result.output.lower())
            self.assertFalse(Path(f"{AGENTS}/shebang-cmd-agent").exists())

    def test_import_shebang_in_commands_allow_scripts_bypasses(self):
        """--allow-scripts bypasses the shebang gate for commands/ files."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init"])
            zip_path = self._make_agent_zip(
                self.runner, "shebang-allow-agent", with_shebang_cmd=True
            )
            self.runner.invoke(cli, ["uninstall", "shebang-allow-agent"], input="y\n")

            result = self.runner.invoke(
                cli, ["import", str(zip_path), "--allow-scripts"]
            )
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertTrue(Path(f"{AGENTS}/shebang-allow-agent").exists())

    def test_import_no_shebang_no_prompt(self):
        """import does not prompt when commands/ has non-executable files."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init"])
            # Normal commands/ file without shebang
            self.runner.invoke(cli, ["deploy", "no-shebang-agent"])
            Path(f"{AGENTS}/no-shebang-agent/commands/task.md").write_text(
                "# Task\nDo something."
            )
            self.runner.invoke(cli, ["wrap", "no-shebang-agent"])
            zip_path = Path("no-shebang-agent-v1.0.0.zip")
            self.runner.invoke(cli, ["uninstall", "no-shebang-agent"], input="y\n")

            result = self.runner.invoke(cli, ["import", str(zip_path)])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertNotIn("executable script", result.output.lower())


if __name__ == '__main__':
    unittest.main()
