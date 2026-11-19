"""Project-level commands: init, adapter add, brief.

Split out of cli.py (#190); `agent_gen.cli` is the entry point and re-exports these names."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

import click

from ..librarian import (
    _FORMAT_REGISTRY,
    CONTEXT_FILE,
    HARNESS_ROOT,
    Librarian,
    _atomic_write_json,
)
from ._group import _echo, cli
from ._paths import _assert_valid_project_root


@cli.command("init")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    help="Root of the project to initialize (defaults to current directory).",
)
@click.option(
    "--primary",
    default="claude",
    show_default=True,
    type=click.Choice(list(_FORMAT_REGISTRY.keys())),
    help="Primary CLI adapter — root symlinks will point to this adapter's compiled brief.",
)
def init_project(project_root: str, primary: str):
    """
    Initialize the AgentFactory harness in a project.

    Creates .ai/ with all harness directories, a single .ai/AgentFactory.md
    source of truth, and wires root symlinks so every CLI tool (Claude,
    Codex, Gemini) reads the same shared context file.

    Safe to run on an existing project — skips items that already exist.
    """
    from datetime import datetime

    project_path = Path(project_root).resolve()
    ai_root = project_path / HARNESS_ROOT

    _echo(f"[librarian] Initializing harness at {project_path} ...")

    # 1. Create .ai/ directory tree
    dirs = [
        ai_root / "adapters" / "claude",
        ai_root / "adapters" / "gemini",
        ai_root / "adapters" / "antigravity",
        ai_root / "adapters" / "codex",
        ai_root / "rules",
        ai_root / "commands",
        ai_root / "skills",
        ai_root / "agents",
        ai_root / "memory",
    ]
    for d in dirs:
        created = not d.exists()
        d.mkdir(parents=True, exist_ok=True)
        if created:
            (d / ".gitkeep").touch()
        _echo(f"  [ok] {d.relative_to(project_path)}")

    # 2. Scaffold milestones.md traceability matrix in .ai/memory/
    milestones_path = ai_root / "memory" / "milestones.md"
    if not milestones_path.exists():
        milestones_path.write_text(
            "# Milestones\n"
            "<!-- version: 1.0.0 -->\n\n"
            "Traceability matrix for all project issues and work items.\n"
            "Update on every PR merge and release (see git-versioning SKILL.md Step 8.5).\n\n"
            "## Completed\n\n"
            "| # | Title | Type | PR | Commit | Tag |\n"
            "|---|-------|------|----|--------|-----|\n"
            "| — | _No items yet_ | — | — | — | — |\n\n"
            "## Pending\n\n"
            "| # | Title | Type | Status | Phase | Branch | PR | Commit | Tag |\n"
            "|---|-------|------|--------|-------|--------|----|--------|-----|\n"
            "| — | _No items yet_ | — | — | — | — | — | — | — |\n",
            encoding="utf-8",
        )
        _echo("  [created] .ai/memory/milestones.md")
    else:
        _echo("  [skip] .ai/memory/milestones.md (already exists)")

    # 3. Create single AgentFactory.md source of truth
    context_path = ai_root / CONTEXT_FILE
    if not context_path.exists():
        context_path.write_text(
            "# Project Context\n\n"
            "<!-- @agent-registry:start -->\n"
            "_No agents currently imported._\n"
            "<!-- @agent-registry:end -->\n\n"
            "<!-- @skills-registry:start -->\n"
            "_No global skills currently imported._\n"
            "<!-- @skills-registry:end -->\n",
            encoding="utf-8",
        )
        _echo(f"  [created] {context_path.relative_to(project_path)}")
    else:
        _echo(f"  [skip] {context_path.relative_to(project_path)} (already exists)")

    # 3. Create .ai/agent-manifest.json
    global_manifest_path = Librarian._global_manifest_path(str(project_path))
    if not global_manifest_path.exists():
        manifest = {
            "factory": "AgentFactory",
            "created_at": datetime.now(UTC).isoformat(),
            "agents": {},
        }
        _atomic_write_json(global_manifest_path, manifest)
        _echo(f"  [created] {global_manifest_path.relative_to(project_path)}")
    else:
        _echo(f"  [skip] {global_manifest_path.relative_to(project_path)} (already exists)")

    # 4. Write default config files for all adapters (idempotent — never clobbers edited files)
    for _adapter_name, _adapter_cfg in _FORMAT_REGISTRY.items():
        _cfg_path = ai_root / "adapters" / _adapter_name / _adapter_cfg["config_file"]
        if not _cfg_path.exists() and _adapter_cfg["config_default"]:
            _cfg_path.write_text(_adapter_cfg["config_default"], encoding="utf-8")

    # 5. Compile adapter briefs and wire adapter symlinks
    Librarian._ensure_adapter_wiring(str(project_path))
    Librarian._compile_adapter_briefs(str(project_path))
    _echo("  [wired] adapter capability symlinks + compiled briefs")

    # 5. Root symlinks — all adapters whose brief has been compiled
    fallback_target = f"{HARNESS_ROOT}/{CONTEXT_FILE}"
    for _name, _cfg in _FORMAT_REGISTRY.items():
        _brief_target = f"{HARNESS_ROOT}/adapters/{_name}/{_cfg['output']}"
        _target = _brief_target if (project_path / _brief_target).exists() else fallback_target
        for root_file in _cfg["root_files"]:
            link_path = project_path / root_file
            if link_path.exists() or link_path.is_symlink():
                _echo(f"  [skip] {root_file} (already exists)")
                continue
            link_path.symlink_to(_target)
            _echo(f"  [linked] {root_file} -> {_target}")

    # Folder symlinks for all adapters (not adapter-specific)
    for adapter_name in _FORMAT_REGISTRY:
        folder_symlink = _FORMAT_REGISTRY[adapter_name]["folder_symlink"]
        link_path = project_path / folder_symlink
        target = f"{HARNESS_ROOT}/adapters/{adapter_name}"
        if link_path.exists() or link_path.is_symlink():
            _echo(f"  [skip] {folder_symlink} (already exists)")
            continue
        link_path.symlink_to(target)
        _echo(f"  [linked] {folder_symlink} -> {target}")

    _echo("\n[librarian] Harness ready. Run 'agentfactory-gen deploy <name>' to scaffold your first agent.")


@cli.group("adapter")
def adapter_group():
    """Manage CLI adapters (activate, rewire, recompile briefs)."""


@adapter_group.command("add")
@click.argument("name", type=click.Choice(list(_FORMAT_REGISTRY.keys())))
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    help="Root of the project to activate the adapter in.",
)
@click.option(
    "--check-completeness",
    is_flag=True,
    default=False,
    help="After compiling, run skill-completeness-check.py on over-budget skills (uses your Claude subscription via Claude Code; ANTHROPIC_API_KEY is an optional fallback).",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="With --check-completeness: exit non-zero if any skill scores below the adapter threshold.",
)
def adapter_add(name: str, project_root: str, check_completeness: bool, strict: bool):
    """
    Activate a CLI adapter mid-project.

    Creates the adapter directory, writes the default config file if absent,
    wires capability symlinks, compiles brief.md, then creates root symlinks.
    Idempotent — re-running recompiles the brief but does not overwrite edited configs.
    """
    project_path = _assert_valid_project_root(project_root)
    ai_root = project_path / HARNESS_ROOT

    config = _FORMAT_REGISTRY[name]
    adapter_dir = ai_root / "adapters" / name

    # 1. Create adapter directory
    created = not adapter_dir.exists()
    adapter_dir.mkdir(parents=True, exist_ok=True)
    if created:
        _echo(f"  [created] {adapter_dir.relative_to(project_path)}")
    else:
        _echo(f"  [exists] {adapter_dir.relative_to(project_path)}")

    # 2. Write default config file if missing (don't clobber user-edited configs)
    config_path = adapter_dir / config["config_file"]
    if not config_path.exists():
        config_path.write_text(config["config_default"], encoding="utf-8")
        _echo(f"  [created] {config_path.relative_to(project_path)}")
    else:
        _echo(f"  [skip] {config_path.relative_to(project_path)} (already exists)")

    # 3. Wire capability symlinks for this adapter
    for link_name, link_target in config["wiring"].items():
        link_path = adapter_dir / link_name
        if link_path.is_symlink():
            _echo(f"  [skip] {link_path.relative_to(project_path)} (already linked)")
            continue
        elif link_path.exists():
            _echo(f"  [skip] {link_path.relative_to(project_path)} (real file — not clobbered)")
            continue
        link_path.symlink_to(link_target)
        _echo(f"  [linked] {link_path.relative_to(project_path)} -> {link_target}")

    # 4. Compile brief.md
    from ..librarian import _FORMATTER_DISPATCH  # noqa: F401 (already imported transitively)

    data = {
        "skills": Librarian._collect_skills_data(str(project_path)),
        "agents": Librarian._collect_agents_data(str(project_path)),
        "commands": Librarian._collect_commands_data(str(project_path)),
        "rules": Librarian._collect_rules_data(str(project_path)),
    }
    brief_path = adapter_dir / config["output"]
    try:
        new_content = Librarian._render_brief(name, config, data)
        brief_path.write_text(new_content, encoding="utf-8")
        _echo(f"  [compiled] {brief_path.relative_to(project_path)}")
    except Exception as exc:
        raise click.ClickException(f"Failed to compile brief for '{name}': {exc}") from exc

    # 5. Create root symlink(s) only now that brief exists
    brief_target = f"{HARNESS_ROOT}/adapters/{name}/{config['output']}"
    for root_file in config["root_files"]:
        root_path = project_path / root_file
        if root_path.exists() and not root_path.is_symlink():
            _echo(f"  [skip] {root_file} (regular file — not clobbered)")
            continue
        if root_path.is_symlink():
            root_path.unlink()
        root_path.symlink_to(brief_target)
        _echo(f"  [linked] {root_file} -> {brief_target}")

    # 6. Folder symlink
    folder_symlink = config["folder_symlink"]
    folder_path = project_path / folder_symlink
    folder_target = f"{HARNESS_ROOT}/adapters/{name}"
    if folder_path.exists() or folder_path.is_symlink():
        _echo(f"  [skip] {folder_symlink} (already exists)")
    else:
        folder_path.symlink_to(folder_target)
        _echo(f"  [linked] {folder_symlink} -> {folder_target}")

    _echo(f"\n[librarian] Adapter '{name}' activated.")

    # 7. Completeness gate — check skill sizes against adapter budget
    _adapter_completeness_gate(
        name=name,
        config=config,
        project_path=project_path,
        ai_root=ai_root,
        check_completeness=check_completeness,
        strict=strict,
    )


def _load_completeness_threshold(adapter: str, ai_root: Path) -> int:
    """Read per-adapter threshold from .ai/config/completeness.json.

    Resolution order: adapter-specific → default key → 90.
    Falls back to 90 on any read/parse error.
    """
    import json as _json

    config_path = ai_root / "config" / "completeness.json"
    try:
        data = _json.loads(config_path.read_text(encoding="utf-8"))
        block = data.get("completeness", {})
        return int(block.get("thresholds", {}).get(adapter, block.get("default", 90)))
    except (FileNotFoundError, KeyError, ValueError, _json.JSONDecodeError):
        return 90


def _adapter_completeness_gate(
    name: str,
    config: dict,
    project_path: Path,
    ai_root: Path,
    check_completeness: bool,
    strict: bool,
) -> None:
    """Warn when skill files exceed the adapter's character budget.

    With check_completeness=True, also runs skill-completeness-check.py on
    each over-budget skill (Claude subscription first, ANTHROPIC_API_KEY optional).  With strict=True,
    exits non-zero if any skill scores below the adapter threshold.
    """
    import subprocess
    import sys

    skills_dir = ai_root / "skills"
    if not skills_dir.exists():
        return

    char_limit: int = config.get("skill_char_limit", 18_000)
    # Config file takes precedence over FORMAT_REGISTRY default
    threshold: int = _load_completeness_threshold(name, ai_root)
    reports_dir = ai_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    over_budget: list[tuple[str, int]] = []
    for skill_dir in sorted(skills_dir.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        size = skill_md.stat().st_size
        if size > char_limit:
            over_budget.append((skill_dir.name, size))

    if not over_budget:
        _echo(f"  [ok] all skills within {char_limit:,} byte limit for '{name}'")
        return

    _echo(f"\n  ⚠  {len(over_budget)} skill(s) exceed the '{name}' adapter limit ({char_limit:,} bytes):")
    for skill_name, size in over_budget:
        excess = size - char_limit
        _echo(f"     {skill_name}: {size:,} bytes (+{excess:,} over budget)")
        _echo(f"     → python3 .ai/scripts/skill-completeness-check.py --skill {skill_name} --threshold {threshold}")

    if not check_completeness:
        _echo("\n  Tip: re-run with --check-completeness to score each skill automatically.")
        return

    # Run completeness check for each over-budget skill
    import os

    check_script = project_path / ".ai" / "scripts" / "skill-completeness-check.py"
    if not check_script.exists():
        _echo(f"\n  ⚠  completeness script not found: {check_script}")
        return

    access = subprocess.run(
        [sys.executable, str(check_script), "--check-access"],
        cwd=str(project_path),
        capture_output=True,
        text=True,
    )
    if access.returncode != 0:
        if "--check-access" in access.stderr:  # project has a pre-2.1 oracle script
            if not os.environ.get("ANTHROPIC_API_KEY"):
                _echo("\n  ⚠  --check-completeness: this project's oracle script needs ANTHROPIC_API_KEY.")
                _echo("     Update .ai/scripts/skill-completeness-check.py to v2.1+ to use your Claude subscription.")
                return
        else:
            _echo("\n  ⚠  --check-completeness: no Claude access.")
            _echo("     Run `claude auth login` (subscription), or export ANTHROPIC_API_KEY (optional fallback).")
            return

    _echo("\n  Running completeness checks …")
    any_failed = False
    for skill_name, _ in over_budget:
        report_path = reports_dir / f"skill-{skill_name}-{name}-completeness.json"
        result = subprocess.run(
            [
                sys.executable,
                str(check_script),
                "--skill",
                skill_name,
                "--threshold",
                str(threshold),
                "--out",
                str(report_path),
                "--quiet",
            ],
            cwd=str(project_path),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            _echo(f"  [pass] {skill_name}")
        elif result.returncode == 1:
            _echo(f"  [warn] {skill_name} — score below {threshold}%")
            if strict:
                any_failed = True
        else:
            _echo(f"  [error] {skill_name} — {result.stderr.strip()[:120]}")

    _echo(f"\n  Reports saved to {reports_dir.relative_to(project_path)}/")
    if any_failed and strict:
        raise click.ClickException(
            f"One or more skills scored below the {threshold}% threshold for '{name}'. "
            "Trim the skill(s) and re-run, or use --no-strict to treat as warning."
        )


@cli.command("brief")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    help="Root of the project to recompile briefs for.",
)
def brief_cmd(project_root: str):
    """
    Recompile all active adapter briefs and update AgentFactory.md.

    Regenerates brief.md for every adapter directory that exists, using the
    current skills, agents, commands, and rules from .ai/.
    """
    project_path = _assert_valid_project_root(project_root)
    ai_root = project_path / HARNESS_ROOT

    Librarian.update_harness_files(str(project_path))

    context_path = ai_root / CONTEXT_FILE
    _echo(f"  [ok] {context_path.relative_to(project_path)}")

    adapters_root = ai_root / "adapters"
    for adapter_name, config in _FORMAT_REGISTRY.items():
        adapter_dir = adapters_root / adapter_name
        brief_path = adapter_dir / config["output"]
        if brief_path.exists():
            root_files_str = ", ".join(config["root_files"])
            _echo(f"  [ok] {brief_path.relative_to(project_path)}  ({root_files_str})")

    _echo("\n[librarian] Briefs regenerated.")
