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
            self.assertIn("Warning", result.output + (result.stderr if hasattr(result, "stderr") else ""))

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
        """--primary codex links AGENTS.md and CODEX.md to codex brief."""
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
            # CLAUDE.md should NOT be created (not primary)
            self.assertFalse(os.path.exists("CLAUDE.md"))

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

    def test_adapter_add_skips_non_symlink_root_file(self):
        """adapter add does not clobber an existing regular-file AGENTS.md."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init", "--primary", "claude"])
            # Create a real file at AGENTS.md
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

    def test_brief_cmd_regenerates_all(self):
        """brief command updates AgentFactory.md and all active adapter briefs."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ["init"])
            result = self.runner.invoke(cli, ["brief"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("brief.md", result.output)
            self.assertIn("ok", result.output)

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


if __name__ == '__main__':
    unittest.main()
