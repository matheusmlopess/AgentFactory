"""agent-gen CLI — deploy, wrap, import."""

import os
import sys
from pathlib import Path

import click

from .librarian import TRACKED_DIRS, HARNESS_ROOT, CONTEXT_FILE, Librarian


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent_root(name: str) -> Path:
    new = Path.cwd() / HARNESS_ROOT / "agents" / name
    legacy = Path.cwd() / "agents" / name
    # Backward-compat: fall back to legacy path if .ai/agents/ doesn't exist yet
    if not new.parent.exists() and legacy.parent.exists():
        return legacy
    return new


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group()
def cli():
    """Agent Factory — Librarian-powered agent lifecycle manager."""


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

@cli.command("init")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    help="Root of the project to initialize (defaults to current directory).",
)
def init_project(project_root: str):
    """
    Initialize the AgentFactory harness in a project.

    Creates .ai/ with all harness directories, a single .ai/.CLAUDE.md
    source of truth, and wires root symlinks so every CLI tool (Claude,
    Codex, Gemini) reads the same shared context file.

    Safe to run on an existing project — skips items that already exist.
    """
    import json as _json
    from datetime import datetime, timezone

    project_path = Path(project_root).resolve()
    ai_root = project_path / HARNESS_ROOT

    click.echo(f"[librarian] Initializing harness at {project_path} ...")

    # 1. Create .ai/ directory tree
    dirs = [
        ai_root / "adapters" / "claude",
        ai_root / "adapters" / "gemini",
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
        click.echo(f"  [ok] {d.relative_to(project_path)}")

    # 2. Create single .CLAUDE.md source of truth
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
        click.echo(f"  [created] {context_path.relative_to(project_path)}")
    else:
        click.echo(f"  [skip] {context_path.relative_to(project_path)} (already exists)")

    # 3. Create .ai/agent-manifest.json
    global_manifest_path = Librarian._global_manifest_path(str(project_path))
    if not global_manifest_path.exists():
        manifest = {
            "factory": "AgentFactory",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "agents": {},
        }
        with open(global_manifest_path, "w") as f:
            _json.dump(manifest, f, indent=2)
        click.echo(f"  [created] {global_manifest_path.relative_to(project_path)}")
    else:
        click.echo(f"  [skip] {global_manifest_path.relative_to(project_path)} (already exists)")

    # 4. Root symlinks — all four .md files point to .ai/.CLAUDE.md
    root_links = {
        "CLAUDE.md":  f"{HARNESS_ROOT}/{CONTEXT_FILE}",
        "AGENTS.md":  f"{HARNESS_ROOT}/{CONTEXT_FILE}",
        "GEMINI.md":  f"{HARNESS_ROOT}/{CONTEXT_FILE}",
        "CODEX.md":   f"{HARNESS_ROOT}/{CONTEXT_FILE}",
        ".claude":    f"{HARNESS_ROOT}/adapters/claude",
        ".gemini":    f"{HARNESS_ROOT}/adapters/gemini",
        ".codex":     f"{HARNESS_ROOT}/adapters/codex",
    }
    for link_name, target in root_links.items():
        link_path = project_path / link_name
        if link_path.exists() or link_path.is_symlink():
            click.echo(f"  [skip] {link_name} (already exists)")
            continue
        link_path.symlink_to(target)
        click.echo(f"  [linked] {link_name} -> {target}")

    # 5. Ensure adapter capability symlinks are wired
    Librarian._ensure_adapter_wiring(str(project_path))
    click.echo("  [wired] adapter capability symlinks")

    click.echo(f"\n[librarian] Harness ready. Run 'agent-gen deploy <name>' to scaffold your first agent.")


# ---------------------------------------------------------------------------
# deploy
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("name")
def deploy(name: str):
    """
    Deploy a new agent directory and initialise its manifest.

    Creates:  agents/<name>/{skills,commands,docs,scripts,orchestration}/  + agent-manifest.json
    """
    root = _agent_root(name)

    if root.exists():
        click.echo(f"[librarian] Agent '{name}' already exists at {root}.", err=True)
        sys.exit(1)

    # Scaffold directories
    for d in TRACKED_DIRS:
        (root / d).mkdir(parents=True)
        (root / d / ".gitkeep").touch()

    # Initialise manifest
    librarian = Librarian(str(root))
    manifest = librarian.init(name)

    click.echo(f"[librarian] Deployed '{name}'")
    click.echo(f"  Root   : {root}")
    click.echo(f"  Version: {manifest['version']}")
    click.echo(f"  git_ref: {manifest['git_ref']}")
    click.echo(f"  Manifest: {root / 'agent-manifest.json'}")


# ---------------------------------------------------------------------------
# describe
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("name")
@click.option("--desc", help="Description of the agent.")
@click.option("--plan", help="Path to the orchestration plan (relative to agent root).")
def describe(name: str, desc: str, plan: str):
    """
    Update agent metadata (description, orchestration plan).
    """
    root = _agent_root(name)
    librarian = Librarian(str(root))
    
    try:
        manifest = librarian._load_manifest()
    except FileNotFoundError as exc:
        click.echo(f"[librarian] {exc}", err=True)
        sys.exit(1)

    if desc:
        manifest["description"] = desc
    if plan:
        manifest["orchestration_plan"] = plan

    librarian._save_manifest(manifest)
    Librarian.sync_to_global(manifest, ".")
    click.echo(f"[librarian] Updated metadata for '{name}'")


@cli.command()
@click.argument("name")
def uninstall(name: str):
    """
    Remove an agent and its registration.
    """
    root = _agent_root(name)
    librarian = Librarian(str(root))
    
    if not root.exists():
        click.echo(f"[librarian] Agent '{name}' not found at {root}.", err=True)
        sys.exit(1)

    if not click.confirm(f"[librarian] Are you sure you want to uninstall '{name}'?"):
        click.echo("[librarian] Aborted.")
        sys.exit(0)

    click.echo(f"[librarian] Uninstalling '{name}'...")
    librarian.uninstall()
    Librarian.update_harness_files(".")
    click.echo(f"[librarian] Uninstalled '{name}'.")


@cli.command()
@click.argument("name")
def audit(name: str):
    """
    Check an agent for integrity drift and missing metadata.
    """
    root = _agent_root(name)
    librarian = Librarian(str(root))
    
    click.echo(f"[librarian] Auditing '{name}'...")
    report = librarian.audit()
    
    clean = True
    
    if report["broken_resources"]:
        clean = False
        click.echo("[librarian] ✗ Broken resources (listed in manifest but missing on disk):", err=True)
        for p in report["broken_resources"]:
            click.echo(f"  - {p}", err=True)

    if report["broken_dependencies"]:
        clean = False
        click.echo("[librarian] ✗ Broken dependencies (cross-file references not found):", err=True)
        for p in report["broken_dependencies"]:
            click.echo(f"  - {p}", err=True)

    if report["untracked_files"]:
        clean = False
        click.echo("[librarian] ! Untracked files (exist on disk but missing from manifest):")
        for p in report["untracked_files"]:
            click.echo(f"  - {p} (Run 'wrap' or 'sync' to add them)")

    if report["missing_skill_manifests"]:
        clean = False
        click.echo("[librarian] ! Missing skill-manifest.json in directories:")
        for p in report["missing_skill_manifests"]:
            click.echo(f"  - {p}")

    if report.get("invalid_skill_manifests"):
        clean = False
        click.echo("[librarian] ✗ Invalid skill manifests (missing 'name' or 'description'):", err=True)
        for p in report["invalid_skill_manifests"]:
            click.echo(f"  - {p}", err=True)

    if clean:
        click.echo(f"[librarian] ✓ '{name}' integrity is clean.")
    else:
        sys.exit(1)


# ---------------------------------------------------------------------------
# wrap
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("name")
@click.option(
    "--out",
    default=".",
    show_default=True,
    help="Directory to write the archive to.",
)
def wrap(name: str, out: str):
    """
    Validate and bundle an agent into a portable .zip package.
    """
    root = _agent_root(name)
    librarian = Librarian(str(root))

    click.echo(f"[librarian] Syncing manifest for '{name}'...")
    librarian.sync()

    click.echo(f"[librarian] Auditing '{name}'...")
    report = librarian.audit()
    
    if report["broken_resources"] or report["broken_dependencies"] or report.get("invalid_skill_manifests"):
        click.echo("[librarian] Audit failed — fix broken paths, dependencies, or invalid skill manifests before wrapping.", err=True)
        click.echo(f"[librarian] Run 'agent-gen audit {name}' for details.", err=True)
        sys.exit(1)

    click.echo("[librarian] Audit passed.")

    try:
        archive = librarian.wrap(out)
    except FileNotFoundError as exc:
        click.echo(f"[librarian] {exc}", err=True)
        sys.exit(1)

    click.echo(f"[librarian] Wrapped → {archive}")


@cli.command()
@click.argument("path")
@click.option("--yes", is_flag=True, help="Execute migration without asking for confirmation.")
def retrofit(path: str, yes: bool):
    """
    Ingest and standardize an existing agent directory.

    Heuristically detects Claude/Gemini/Codex structures and maps them
    to the AgentFactory standard.
    """
    source_path = Path(path).resolve()
    if not source_path.exists():
        click.echo(f"[librarian] Path not found: {source_path}", err=True)
        sys.exit(1)

    click.echo(f"[librarian] Analyzing {source_path}...")
    profile, mapping = Librarian.propose_retrofit(str(source_path))

    click.echo(f"[librarian] Detected profile: {profile.upper()}")
    click.echo("[librarian] Proposed Mapping:")
    for src, dest in mapping.items():
        click.echo(f"  - {src} -> {dest}")

    if not yes:
        if not click.confirm("[librarian] Proceed with migration?"):
            click.echo("[librarian] Aborted.")
            sys.exit(0)

    # In-place migration
    librarian = Librarian(str(source_path))
    librarian.migrate(mapping)
    
    # Initialize manifest if missing, otherwise sync
    if not librarian.manifest_path.exists():
        name = source_path.name
        librarian.init(name)
    
    librarian.sync()

    click.echo(f"[librarian] Retrofit complete for '{source_path.name}'.")
    click.echo(f"  Standardized into {TRACKED_DIRS}")


# ---------------------------------------------------------------------------
# import-skill
# ---------------------------------------------------------------------------

@cli.command("import-skill")
@click.argument("path")
@click.option(
    "--to",
    "target_agent",
    default=".",
    help="Name of the target agent to receive the skill. Defaults to '.' (the root project).",
)
def import_skill(path: str, target_agent: str):
    """
    Import a standalone skill into an existing agent or the root project.
    """
    path_obj = Path(path).resolve()
    if not path_obj.exists():
        click.echo(f"[librarian] Skill path not found: {path_obj}", err=True)
        sys.exit(1)

    if target_agent == ".":
        target_root = Path.cwd() / HARNESS_ROOT
        click.echo(f"[librarian] Importing skill from {path_obj} into root project...")
        # Perform root-level skill import logic manually to avoid overwriting global manifest
        import tempfile
        import shutil
        import zipfile
        import json

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            if zipfile.is_zipfile(path_obj):
                with zipfile.ZipFile(path_obj, 'r') as zf:
                    zf.extractall(temp_path)
            elif path_obj.is_dir():
                shutil.copytree(path_obj, temp_path, dirs_exist_ok=True)
            else:
                click.echo("[librarian] Skill source must be a directory or a ZIP file.", err=True)
                sys.exit(1)

            manifest_file = temp_path / "skill-manifest.json"
            if not manifest_file.exists():
                manifests = list(temp_path.rglob("skill-manifest.json"))
                if not manifests:
                    click.echo("[librarian] skill-manifest.json not found in the source.", err=True)
                    sys.exit(1)
                manifest_file = manifests[0]
                temp_path = manifest_file.parent

            with open(manifest_file) as f:
                skill_data = json.load(f)

            skill_name = skill_data["name"]
            target_dir = target_root / "skills" / skill_name
            target_dir.parent.mkdir(parents=True, exist_ok=True)

            if target_dir.exists():
                shutil.rmtree(target_dir)

            shutil.copytree(temp_path, target_dir)

        click.echo(f"[librarian] Successfully imported skill '{skill_name}' into root project.")
        click.echo(f"  Path: {target_root / 'skills' / skill_name}")  # .ai/skills/<name>
        
        # update_harness_files takes the project root (not the .ai/ sub-path)
        Librarian.update_harness_files(str(Path.cwd()))
        return

    target_root = _agent_root(target_agent)
    if not target_root.exists():
        click.echo(f"[librarian] Target agent '{target_agent}' not found at {target_root}.", err=True)
        sys.exit(1)

    librarian = Librarian(str(target_root))
    
    try:
        click.echo(f"[librarian] Importing skill from {path_obj} into '{target_agent}'...")
        skill_name = librarian.import_skill(str(path_obj))
        click.echo(f"[librarian] Successfully imported skill '{skill_name}' into '{target_agent}'.")
        click.echo(f"  Path: {target_root / 'skills' / skill_name}")
    except Exception as exc:
        click.echo(f"[librarian] Skill import failed: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# import (reserved word workaround)
# ---------------------------------------------------------------------------

@cli.command("import")
@click.argument("zip_path")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    help="Root of the project receiving the import (for the Handshake).",
)
def import_agent(zip_path: str, project_root: str):
    """
    Unpack a portable agent bundle and register it in this project.

    Steps:
      1. Unpack <zip_path> into agents/<name>/
      2. Read the embedded manifest
      3. Handshake: update this project's global agent-manifest.json
    """
    zip_path = Path(zip_path).resolve()

    if not zip_path.exists():
        click.echo(f"[librarian] File not found: {zip_path}", err=True)
        sys.exit(1)

    # Peek at the archive to get the agent name before unpacking
    import zipfile, json

    with zipfile.ZipFile(zip_path) as zf:
        with zf.open("agent-manifest.json") as mf:
            peeked = json.load(mf)

    name = peeked["name"]
    target_root = _agent_root(name)

    if target_root.exists():
        click.echo(
            f"[librarian] '{name}' already exists at {target_root}. "
            "Remove it first or rename the incoming bundle.",
            err=True,
        )
        sys.exit(1)

    import tempfile
    import shutil

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir) / name
        temp_root.mkdir(parents=True)
        
        click.echo(f"[librarian] Unpacking '{name}'...")
        manifest = Librarian.unpack(str(zip_path), str(temp_root))

        # Deep Audit before finalizing
        click.echo(f"[librarian] Auditing '{name}' before registration...")
        librarian = Librarian(str(temp_root))
        report = librarian.audit()
        if report["broken_resources"] or report["broken_dependencies"] or report.get("invalid_skill_manifests"):
            click.echo("[librarian] Audit FAILED for imported bundle. Aborting...", err=True)
            sys.exit(1)

        # Move to final location
        target_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(temp_root), str(target_root))

    click.echo(f"[librarian] Registering '{name}' in project manifest...")
    Librarian.register_in_project(manifest, project_root)

    # Success summary (paste-ready for Claude)
    skills = manifest["resources"].get("skills", [])
    commands = manifest["resources"].get("commands", [])
    docs = manifest["resources"].get("docs", [])
    scripts = manifest["resources"].get("scripts", [])
    orchestration = manifest["resources"].get("orchestration", [])

    click.echo("")
    click.echo("=" * 60)
    click.echo("Librarian: Import Complete.")
    click.echo(
        f"  Added {len(skills)} skill(s), {len(commands)} command(s), "
        f"{len(docs)} doc(s), {len(scripts)} script(s), "
        f"and {len(orchestration)} orchestration file(s) to your environment."
    )
    click.echo(f"  You are now configured as the '{name}' agent.")
    if docs:
        claude_md = next((d for d in docs if "CLAUDE.md" in d), None)
        if claude_md:
            click.echo(f"  Check {claude_md} for your new instructions.")
    click.echo("=" * 60)

if __name__ == "__main__":
    cli()
