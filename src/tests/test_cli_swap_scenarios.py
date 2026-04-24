"""
CLI swap scenario tests — all adapter permutations.

Tier 1 (CI-safe): Uses CliRunner + isolated_filesystem to simulate every
init → adapter-add → brief recompile permutation across claude, codex, gemini.
Verifies YOU ARE HERE marker, Project Context, per-adapter format differences,
cross-adapter table completeness, and root file wiring.

Tier 2 (live): Marked @pytest.mark.live. Invokes actual CLIs (claude / codex /
gemini) via subprocess. Skips automatically when the CLI is not installed.

Run Tier 1 only:
    pytest src/tests/test_cli_swap_scenarios.py -m "not live" -v

Run Tier 2 (live CLIs required):
    pytest src/tests/test_cli_swap_scenarios.py -m live -v
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_gen.cli import cli
from agent_gen.librarian import HARNESS_ROOT

pytestmark = pytest.mark.integration


@pytest.fixture
def runner():
    return CliRunner()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _add_skill(root: Path, name: str, desc: str = "Test skill") -> None:
    sd = root / HARNESS_ROOT / "skills" / name
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "skill-manifest.json").write_text(
        json.dumps({"name": name, "description": desc,
                    "triggers": f"when you need {name}", "input": ""}),
        encoding="utf-8",
    )


def _brief(adapter: str) -> Path:
    return Path(f".ai/adapters/{adapter}/brief.md")


def _read_brief(adapter: str) -> str:
    return _brief(adapter).read_text(encoding="utf-8")


def _you_are_here_row(content: str) -> str:
    """Return the line containing ← YOU ARE HERE, or empty string."""
    for line in content.splitlines():
        if "← YOU ARE HERE" in line:
            return line
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Class A — init with each primary adapter
# ─────────────────────────────────────────────────────────────────────────────

class TestInitPrimary:
    """init --primary <adapter> creates all root files + correct YOU ARE HERE."""

    @pytest.mark.parametrize("adapter", ["claude", "codex", "gemini"])
    def test_init_exit_zero(self, runner, adapter):
        with runner.isolated_filesystem():
            r = runner.invoke(cli, ["init", "--primary", adapter])
            assert r.exit_code == 0, r.output

    @pytest.mark.parametrize("adapter", ["claude", "codex", "gemini"])
    def test_you_are_here_on_correct_row(self, runner, adapter):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", adapter])
            content = _read_brief(adapter)
            row = _you_are_here_row(content)
            assert row, f"← YOU ARE HERE not found in {adapter} brief"
            assert adapter in row, \
                f"YOU ARE HERE row does not mention '{adapter}': {row!r}"

    @pytest.mark.parametrize("adapter", ["claude", "codex", "gemini"])
    def test_you_are_here_appears_exactly_once(self, runner, adapter):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", adapter])
            content = _read_brief(adapter)
            assert content.count("← YOU ARE HERE") == 1

    @pytest.mark.parametrize("adapter", ["claude", "codex", "gemini"])
    def test_project_context_present(self, runner, adapter):
        """## Project Context injected once preamble is written to AgentFactory.md."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", adapter])
            # Write a preamble (fresh init leaves AF.md empty of preamble)
            af = Path(".ai/AgentFactory.md")
            original = af.read_text(encoding="utf-8")
            af.write_text("## Overview\n\nTest project description.\n\n" + original,
                          encoding="utf-8")
            runner.invoke(cli, ["brief"])
            content = _read_brief(adapter)
            assert "## Project Context" in content, \
                f"## Project Context missing from {adapter} brief"

    @pytest.mark.parametrize("adapter,root_files", [
        ("claude", ["CLAUDE.md"]),
        ("codex",  ["AGENTS.md", "CODEX.md"]),
        ("gemini", ["GEMINI.md"]),
    ])
    def test_root_files_exist_for_primary(self, runner, adapter, root_files):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", adapter])
            for f in root_files:
                assert Path(f).is_symlink(), f"{f} not a symlink after init --primary {adapter}"


# ─────────────────────────────────────────────────────────────────────────────
# Class B — directed swap scenarios (all 6 ordered pairs)
# ─────────────────────────────────────────────────────────────────────────────

class TestAdapterSwap:
    """Init with one adapter then activate a second. Verify YOU ARE HERE and root files."""

    def _swap(self, runner, init_primary: str, add_adapter: str):
        runner.invoke(cli, ["init", "--primary", init_primary])
        r = runner.invoke(cli, ["adapter", "add", add_adapter])
        assert r.exit_code == 0, r.output
        runner.invoke(cli, ["brief"])
        return _read_brief(add_adapter)

    def test_claude_to_codex(self, runner):
        with runner.isolated_filesystem():
            content = self._swap(runner, "claude", "codex")
            row = _you_are_here_row(content)
            assert "codex" in row
            assert Path("AGENTS.md").is_symlink()
            assert Path("CODEX.md").is_symlink()

    def test_claude_to_gemini(self, runner):
        with runner.isolated_filesystem():
            content = self._swap(runner, "claude", "gemini")
            row = _you_are_here_row(content)
            assert "gemini" in row
            assert Path("GEMINI.md").is_symlink()

    def test_codex_to_claude(self, runner):
        with runner.isolated_filesystem():
            content = self._swap(runner, "codex", "claude")
            row = _you_are_here_row(content)
            assert "claude" in row
            assert Path("CLAUDE.md").is_symlink()

    def test_codex_to_gemini(self, runner):
        with runner.isolated_filesystem():
            content = self._swap(runner, "codex", "gemini")
            row = _you_are_here_row(content)
            assert "gemini" in row
            assert Path("GEMINI.md").is_symlink()

    def test_gemini_to_claude(self, runner):
        with runner.isolated_filesystem():
            content = self._swap(runner, "gemini", "claude")
            row = _you_are_here_row(content)
            assert "claude" in row
            assert Path("CLAUDE.md").is_symlink()

    def test_gemini_to_codex(self, runner):
        with runner.isolated_filesystem():
            content = self._swap(runner, "gemini", "codex")
            row = _you_are_here_row(content)
            assert "codex" in row
            assert Path("AGENTS.md").is_symlink()
            assert Path("CODEX.md").is_symlink()

    def test_swap_preserves_init_adapter_brief(self, runner):
        """Adding a second adapter must not corrupt the first adapter's brief."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "claude"])
            runner.invoke(cli, ["adapter", "add", "codex"])
            runner.invoke(cli, ["brief"])
            claude_content = _read_brief("claude")
            row = _you_are_here_row(claude_content)
            assert "claude" in row, "claude brief YOU ARE HERE row corrupted after adding codex"


# ─────────────────────────────────────────────────────────────────────────────
# Class C — three-way lifecycle from each starting adapter
# ─────────────────────────────────────────────────────────────────────────────

class TestThreeWayLifecycle:
    """Init with A, add B, add C, recompile. Each brief must have exactly one YOU ARE HERE."""

    def _full_lifecycle(self, runner, primary: str):
        """Activate all three adapters starting from `primary`. Return dict of brief contents."""
        others = [a for a in ["claude", "codex", "gemini"] if a != primary]
        runner.invoke(cli, ["init", "--primary", primary])
        for other in others:
            runner.invoke(cli, ["adapter", "add", other])
        runner.invoke(cli, ["brief"])
        return {a: _read_brief(a) for a in ["claude", "codex", "gemini"]}

    @pytest.mark.parametrize("primary", ["claude", "codex", "gemini"])
    def test_each_brief_has_exactly_one_you_are_here(self, runner, primary):
        with runner.isolated_filesystem():
            briefs = self._full_lifecycle(runner, primary)
            for adapter, content in briefs.items():
                count = content.count("← YOU ARE HERE")
                assert count == 1, \
                    f"{adapter} brief has {count} YOU ARE HERE markers (expected 1)"

    @pytest.mark.parametrize("primary", ["claude", "codex", "gemini"])
    def test_each_brief_you_are_here_on_own_row(self, runner, primary):
        with runner.isolated_filesystem():
            briefs = self._full_lifecycle(runner, primary)
            for adapter, content in briefs.items():
                row = _you_are_here_row(content)
                assert adapter in row, \
                    f"{adapter} brief YOU ARE HERE on wrong row: {row!r}"

    @pytest.mark.parametrize("primary", ["claude", "codex", "gemini"])
    def test_all_three_adapters_in_cross_table(self, runner, primary):
        """Cross-adapter table in every brief lists all three adapters."""
        with runner.isolated_filesystem():
            briefs = self._full_lifecycle(runner, primary)
            for adapter, content in briefs.items():
                for listed in ["claude", "codex", "gemini"]:
                    assert listed in content, \
                        f"{adapter} brief missing '{listed}' from cross-adapter table"

    @pytest.mark.parametrize("primary", ["claude", "codex", "gemini"])
    def test_all_root_files_present(self, runner, primary):
        with runner.isolated_filesystem():
            self._full_lifecycle(runner, primary)
            for f in ["CLAUDE.md", "AGENTS.md", "CODEX.md", "GEMINI.md"]:
                assert Path(f).is_symlink(), f"{f} missing after full lifecycle from {primary}"


# ─────────────────────────────────────────────────────────────────────────────
# Class D — adapter-specific format and content assertions
# ─────────────────────────────────────────────────────────────────────────────

class TestBriefContentAssertions:
    """Structural and format checks per adapter."""

    def test_claude_has_commands_section(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "claude"])
            content = _read_brief("claude")
            assert "## Commands" in content

    def test_codex_has_no_commands_section(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "codex"])
            content = _read_brief("codex")
            assert "## Commands" not in content

    def test_gemini_has_no_commands_section(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "gemini"])
            content = _read_brief("gemini")
            assert "## Commands" not in content

    def test_gemini_has_available_tools_header(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "gemini"])
            content = _read_brief("gemini")
            assert "## Available Tools" in content

    def test_all_briefs_reference_agentfactory_md(self, runner):
        """Harness identity block must mention .ai/AgentFactory.md in every brief."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            for adapter in ["claude", "codex", "gemini"]:
                content = _read_brief(adapter)
                assert "AgentFactory.md" in content, \
                    f"AgentFactory.md reference missing from {adapter} brief"

    def test_all_briefs_have_rules_section(self, runner):
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            for adapter in ["claude", "codex", "gemini"]:
                content = _read_brief(adapter)
                assert "## Behavior Rules" in content, \
                    f"## Behavior Rules missing from {adapter} brief"

    def test_section_order_harness_before_context_before_skills(self, runner):
        """## Harness must precede ## Project Context which must precede skills section."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            # Write preamble so ## Project Context is injected
            af = Path(".ai/AgentFactory.md")
            original = af.read_text(encoding="utf-8")
            af.write_text("## Overview\n\nTest project description.\n\n" + original,
                          encoding="utf-8")
            runner.invoke(cli, ["brief"])
            for adapter in ["claude", "codex", "gemini"]:
                content = _read_brief(adapter)
                harness_pos = content.find("## Harness")
                context_pos = content.find("## Project Context")
                skills_pos = max(
                    content.find("## Available Skills"),
                    content.find("## Available Tools"),
                    content.find("## Skills"),
                )
                assert harness_pos < context_pos < skills_pos, (
                    f"{adapter} brief section order wrong: "
                    f"Harness@{harness_pos}, Context@{context_pos}, Skills@{skills_pos}"
                )

    def test_codex_context_truncation_when_preamble_large(self, runner):
        """If preamble exceeds 2000 chars, codex brief gets truncation warning comment."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "codex"])
            # Write a large preamble into AgentFactory.md
            af_path = Path(".ai/AgentFactory.md")
            original = af_path.read_text(encoding="utf-8")
            marker = original.find("<!-- @")
            # Inject a large preamble block before the first marker
            padding = "A" * 2500
            preamble_block = f"\n## Large Context\n\n{padding}\n\n"
            if marker > 0:
                new_content = original[:marker] + preamble_block + original[marker:]
            else:
                new_content = original + preamble_block
            af_path.write_text(new_content, encoding="utf-8")
            # Recompile
            runner.invoke(cli, ["brief"])
            content = _read_brief("codex")
            assert "context truncated" in content, \
                "Codex brief should contain truncation warning when preamble > 2000 chars"

    def test_claude_no_truncation_warning_when_preamble_within_budget(self, runner):
        """Claude 4000-char budget — default preamble should not be truncated."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "claude"])
            content = _read_brief("claude")
            assert "context truncated" not in content

    def test_cross_adapter_table_complete_even_with_one_adapter(self, runner):
        """Even a claude-only init still lists codex and gemini rows in the table."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "claude"])
            content = _read_brief("claude")
            assert "codex" in content
            assert "gemini" in content

    def test_agentfactory_md_gets_rules_and_commands_sections(self, runner):
        """After brief recompile, AgentFactory.md has @rules and @commands marker blocks."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init"])
            runner.invoke(cli, ["brief"])
            af = Path(".ai/AgentFactory.md").read_text(encoding="utf-8")
            assert "<!-- @rules-start -->" in af, \
                "AgentFactory.md missing <!-- @rules-start --> after brief recompile"
            assert "<!-- @commands-start -->" in af, \
                "AgentFactory.md missing <!-- @commands-start --> after brief recompile"

    def test_skill_appears_in_all_adapter_briefs_after_swap(self, runner):
        """A skill added before a swap must appear in the new adapter's brief."""
        with runner.isolated_filesystem():
            runner.invoke(cli, ["init", "--primary", "claude"])
            _add_skill(Path("."), "my-workflow", "Automates the deployment workflow")
            runner.invoke(cli, ["adapter", "add", "codex"])
            runner.invoke(cli, ["brief"])
            for adapter in ["claude", "codex"]:
                content = _read_brief(adapter)
                assert "my-workflow" in content, \
                    f"Skill 'my-workflow' missing from {adapter} brief after swap"


# ─────────────────────────────────────────────────────────────────────────────
# Tier 2 — live agent invocation (pytest -m live)
# ─────────────────────────────────────────────────────────────────────────────

# Probe prompt sent to each agent. Short enough to get a fast response,
# specific enough to verify the agent has read the harness brief.
_PROBE_PROMPT = (
    "What harness root does this project use? "
    "What adapter are you running in? "
    "Name one available skill."
)

# Best-effort CLI flags per agent. Users should verify for their installed version.
_CLI_INVOCATION = {
    "claude": ["claude", "--print", _PROBE_PROMPT],
    "codex":  ["codex",  "exec", "--skip-git-repo-check", _PROBE_PROMPT],
    "gemini": ["gemini", "--prompt", _PROBE_PROMPT],
}

# Keywords that a well-briefed agent should mention.
_EXPECTED_KEYWORDS = {
    "claude": [".ai"],
    "codex":  [".ai"],
    "gemini": [".ai"],
}


@pytest.mark.live
@pytest.mark.parametrize("adapter", ["claude", "codex", "gemini"])
def test_live_agent_acknowledges_harness(adapter, runner, tmp_path):
    """
    Invoke the real CLI agent in a fresh project and assert it acknowledges the
    AgentFactory harness context from its compiled brief.

    Skipped automatically when the CLI is not installed.
    """
    if not shutil.which(adapter):
        pytest.skip(f"{adapter} CLI not installed")

    proj = tmp_path / "live_proj"
    proj.mkdir()

    # Init project in tmp_path
    r = runner.invoke(cli, ["init", "--primary", adapter, "--project-root", str(proj)])
    assert r.exit_code == 0, f"init failed: {r.output}"

    # Add a recognisable skill so there's something concrete to mention
    _add_skill(proj, "deploy-pipeline", "Automates the CI/CD deploy pipeline")
    r2 = runner.invoke(cli, ["brief", "--project-root", str(proj)])
    assert r2.exit_code == 0, f"brief failed: {r2.output}"

    # Invoke the live CLI from the project root
    cmd = _CLI_INVOCATION[adapter]
    proc = subprocess.run(
        cmd,
        cwd=str(proj),
        capture_output=True,
        text=True,
        timeout=120,
    )
    response = (proc.stdout + proc.stderr).lower()

    missing = [kw for kw in _EXPECTED_KEYWORDS[adapter] if kw.lower() not in response]
    assert not missing, (
        f"{adapter} live response did not mention: {missing}\n"
        f"Response excerpt:\n{response[:800]}"
    )
