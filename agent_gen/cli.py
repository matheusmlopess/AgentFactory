"""agent-gen CLI — deploy, wrap, import."""

import os
import sys
from pathlib import Path

import click

from .librarian import TRACKED_DIRS, Librarian


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent_root(name: str) -> Path:
    return Path.cwd() / "agents" / name


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group()
def cli():
    """Agent Factory — Librarian-powered agent lifecycle manager."""


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
    
    if report["broken_resources"] or report["broken_dependencies"]:
        click.echo("[librarian] Audit failed — fix broken paths/dependencies before wrapping.", err=True)
        # We don't list them again as they are listed in audit() logic when we call audit command
        # but here we should at least list them or point to audit command
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
    target_root = Path.cwd() / "agents" / name

    if target_root.exists():
        click.echo(
            f"[librarian] '{name}' already exists at {target_root}. "
            "Remove it first or rename the incoming bundle.",
            err=True,
        )
        sys.exit(1)

    target_root.mkdir(parents=True)

    click.echo(f"[librarian] Unpacking '{name}'...")
    manifest = Librarian.unpack(str(zip_path), str(target_root))

    # Deep Audit before finalizing
    click.echo(f"[librarian] Auditing '{name}' before registration...")
    librarian = Librarian(str(target_root))
    report = librarian.audit()
    if report["broken_resources"] or report["broken_dependencies"]:
        click.echo("[librarian] Audit FAILED for imported bundle. Rollback...", err=True)
        import shutil
        shutil.rmtree(target_root)
        sys.exit(1)

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
