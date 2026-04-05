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

    Creates:  agents/<name>/{skills,commands,docs}/  + agent-manifest.json
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

    Reads agents/<name>/agent-manifest.json, verifies all files exist,
    then writes <name>-v<version>.zip to --out.
    """
    root = _agent_root(name)
    librarian = Librarian(str(root))

    click.echo(f"[librarian] Syncing manifest for '{name}'...")
    librarian.sync()

    click.echo(f"[librarian] Validating '{name}'...")
    present, missing = librarian.validate()

    if missing:
        click.echo(f"[librarian] Validation FAILED — {len(missing)} missing file(s):", err=True)
        for p in missing:
            click.echo(f"  ✗ {p}", err=True)
        sys.exit(1)

    click.echo(f"[librarian] {len(present)} file(s) verified.")

    try:
        archive = librarian.wrap(out)
    except FileNotFoundError as exc:
        click.echo(f"[librarian] {exc}", err=True)
        sys.exit(1)

    click.echo(f"[librarian] Wrapped → {archive}")


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

    click.echo(f"[librarian] Registering '{name}' in project manifest...")
    Librarian.register_in_project(manifest, project_root)

    # Success summary (paste-ready for Claude)
    skills = manifest["resources"].get("skills", [])
    commands = manifest["resources"].get("commands", [])
    docs = manifest["resources"].get("docs", [])

    click.echo("")
    click.echo("=" * 60)
    click.echo("Librarian: Import Complete.")
    click.echo(
        f"  Added {len(skills)} skill(s), {len(commands)} command(s), "
        f"and {len(docs)} doc(s) to your environment."
    )
    click.echo(f"  You are now configured as the '{name}' agent.")
    if docs:
        claude_md = next((d for d in docs if "CLAUDE.md" in d), None)
        if claude_md:
            click.echo(f"  Check {claude_md} for your new instructions.")
    click.echo("=" * 60)
