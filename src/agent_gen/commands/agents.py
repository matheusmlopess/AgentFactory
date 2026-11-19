"""Agent lifecycle commands: deploy, describe, uninstall, audit, wrap, sign, publish, retrofit.

Split out of cli.py (#190); `agent_gen.cli` is the entry point and re-exports these names."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from ..librarian import (
    TRACKED_DIRS,
    Librarian,
)
from . import _remote
from ._group import _echo, cli
from ._paths import _agent_root, _assert_within_root


@cli.command()
@click.argument("name")
def deploy(name: str):
    """
    Deploy a new agent directory and initialise its manifest.

    Creates:  agents/<name>/{skills,commands,docs,scripts,orchestration}/  + agent-manifest.json
    """
    root = _agent_root(name)

    if root.exists():
        _echo(f"[librarian] Agent '{name}' already exists at {root}.", err=True)
        sys.exit(1)

    # Scaffold directories
    for d in TRACKED_DIRS:
        (root / d).mkdir(parents=True)
        (root / d / ".gitkeep").touch()

    # Initialise manifest
    librarian = Librarian(str(root))
    manifest = librarian.init(name)

    # Register in the global project manifest so the agent appears in briefs
    # Only when a harness exists (skip if running outside an init'd project)
    if Librarian._global_manifest_path(str(Path.cwd())).exists():
        Librarian.register_in_project(manifest, str(Path.cwd()))

    _echo(f"[librarian] Deployed '{name}'")
    _echo(f"  Root   : {root}")
    _echo(f"  Version: {manifest['version']}")
    _echo(f"  git_ref: {manifest['git_ref']}")
    _echo(f"  Manifest: {root / 'agent-manifest.json'}")


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
        _echo(f"[librarian] {exc}", err=True)
        sys.exit(1)

    if desc:
        manifest["description"] = desc
    if plan:
        _assert_within_root(plan, root)  # path traversal guard (#59)
        if not (root / plan).exists():
            _echo(f"[librarian] Warning: plan path does not exist: {plan}", err=True)
        manifest["orchestration_plan"] = plan

    librarian._save_manifest(manifest)
    Librarian.sync_to_global(manifest, ".")
    _echo(f"[librarian] Updated metadata for '{name}'")


@cli.command()
@click.argument("name")
def uninstall(name: str):
    """
    Remove an agent and its registration.
    """
    root = _agent_root(name)
    librarian = Librarian(str(root))

    if not root.exists():
        _echo(f"[librarian] Agent '{name}' not found at {root}.", err=True)
        sys.exit(1)

    if not click.confirm(f"[librarian] Are you sure you want to uninstall '{name}'?"):
        _echo("[librarian] Aborted.")
        sys.exit(0)

    _echo(f"[librarian] Uninstalling '{name}'...")
    librarian.uninstall()
    Librarian.update_harness_files(".")
    _echo(f"[librarian] Uninstalled '{name}'.")


@cli.command()
@click.argument("name")
@click.option(
    "--fix",
    is_flag=True,
    default=False,
    help="Auto-sync manifest to resolve untracked-file warnings, then re-audit.",
)
def audit(name: str, fix: bool):
    """
    Check an agent for integrity drift and missing metadata.
    """
    root = _agent_root(name)
    librarian = Librarian(str(root))

    _echo(f"[librarian] Auditing '{name}'...")
    report = librarian.audit()

    # Auto-fix: sync manifest to pick up untracked files, then re-audit
    if fix and report["untracked_files"]:
        _echo(f"[librarian] --fix: syncing {len(report['untracked_files'])} untracked file(s) into manifest...")
        librarian.sync()
        _echo("[librarian] Re-auditing after sync...")
        report = librarian.audit()

    fatal = False

    if report["broken_resources"]:
        fatal = True
        _echo("[librarian] ✗ Broken resources (listed in manifest but missing on disk):", err=True)
        for p in report["broken_resources"]:
            _echo(f"  - {p}", err=True)

    if report["broken_dependencies"]:
        fatal = True
        _echo("[librarian] ✗ Broken dependencies (cross-file references not found):", err=True)
        for p in report["broken_dependencies"]:
            _echo(f"  - {p}", err=True)

    if report.get("invalid_skill_manifests"):
        fatal = True
        _echo("[librarian] ✗ Invalid skill manifests (missing 'name' or 'description'):", err=True)
        for p in report["invalid_skill_manifests"]:
            _echo(f"  - {p}", err=True)

    # Warnings — do not block audit (#132)
    if report["untracked_files"]:
        _echo("[librarian] ! Untracked files (exist on disk but not yet in manifest):")
        for p in report["untracked_files"]:
            _echo(f"  - {p} (run 'agentfactory-gen audit {name} --fix' to register)")

    if report["missing_skill_manifests"]:
        _echo("[librarian] ! Missing skill-manifest.json in skill directories:")
        for p in report["missing_skill_manifests"]:
            _echo(f"  - {p}")

    if report.get("skill_version_drift"):
        _echo("[librarian] ! Skill version drift (SKILL.md ≠ skill-manifest.json):")
        for p in report["skill_version_drift"]:
            _echo(f"  - {p}")

    if fatal:
        _echo(f"[librarian] ✗ '{name}' audit FAILED — fix the issues above.", err=True)
        sys.exit(1)

    if not any([report["untracked_files"], report["missing_skill_manifests"], report.get("skill_version_drift")]):
        _echo(f"[librarian] ✓ '{name}' integrity is clean.")
    else:
        _echo(f"[librarian] ✓ '{name}' integrity OK (warnings above — run sync to resolve).")


@cli.command()
@click.argument("name")
@click.option(
    "--out",
    default=".",
    show_default=True,
    help="Directory to write the archive to (default: current directory).",
)
@click.option(
    "--print-path",
    "print_path",
    is_flag=True,
    default=False,
    help="Print only the archive path to stdout for scripting (e.g. zip=$(agentfactory-gen wrap my-agent --print-path)).",
)
@click.option(
    "--sign",
    "sign_key",
    default=None,
    metavar="SSH_KEY",
    help="Also write <zip>.sig, signed with this SSH private key (e.g. ~/.ssh/id_ed25519); "
    "`publish` uploads it and importers can verify it against your GitHub keys.",
)
def wrap(name: str, out: str, print_path: bool, sign_key: str | None):
    """
    Validate and bundle an agent into a portable .zip package.
    """
    root = _agent_root(name)
    librarian = Librarian(str(root))

    _echo(f"[librarian] Syncing manifest for '{name}'...")
    librarian.sync()

    _echo(f"[librarian] Auditing '{name}'...")
    report = librarian.audit()

    if report["broken_resources"] or report["broken_dependencies"] or report.get("invalid_skill_manifests"):
        _echo(
            "[librarian] Audit failed — fix broken paths, dependencies, or invalid skill manifests before wrapping.",
            err=True,
        )
        _echo(f"[librarian] Run 'agentfactory-gen audit {name}' for details.", err=True)
        sys.exit(1)

    _echo("[librarian] Audit passed.")

    try:
        archive = librarian.wrap(out)
    except FileNotFoundError as exc:
        _echo(f"[librarian] {exc}", err=True)
        sys.exit(1)

    _echo(f"[librarian] Wrapped → {archive}")

    # Emit SHA-256 sidecar so consumers can verify provenance (#144)
    import hashlib as _hashlib

    sha256 = _hashlib.sha256(archive.read_bytes()).hexdigest()
    sidecar = archive.with_suffix(".zip.sha256")
    sidecar.write_text(f"{sha256}  {archive.name}\n", encoding="utf-8")
    _echo(f"[librarian] Checksum → {sidecar}")

    if sign_key:
        from ..signing import SignatureError, sign_file

        try:
            sig = sign_file(archive, Path(sign_key).expanduser())
        except SignatureError as exc:
            _echo(f"[librarian] {exc}", err=True)
            sys.exit(1)
        _echo(f"[librarian] Signature → {sig}")

    # --print-path contract (#136): the archive path is the last line on stdout
    if print_path:
        click.echo(str(archive))


@cli.command()
@click.argument("name")
@click.option("--version", "version_override", default=None, help="Override version from manifest.")
@click.option("--tag", "tags", multiple=True, metavar="TAG", help="Discovery tag (repeatable).")
def publish(name: str, version_override: str, tags: tuple):
    """Upload a wrapped agent to the public registry."""
    root = _agent_root(name)
    librarian = Librarian(str(root))
    manifest = librarian._load_manifest()

    if not manifest.get("description"):
        raise click.ClickException(
            f"Manifest 'description' is required for publishing. "
            f"Run 'agentfactory-gen describe {name} --desc \"...\"' first."
        )

    version = version_override or manifest.get("version", "0.1.0")
    agent_name = manifest["name"]
    zip_name = f"{agent_name}-v{version}.zip"
    zip_path = Path.cwd() / zip_name

    if not zip_path.exists():
        raise click.ClickException(f"No wrapped archive found: {zip_name}\nRun 'agentfactory-gen wrap {name}' first.")

    publish_manifest = {
        "name": agent_name,
        "version": version,
        "description": manifest["description"],
        "tags": list(tags),
    }

    _echo(f"[librarian] Publishing '{agent_name}@{version}' to registry...")
    _remote._registry_publish(publish_manifest, zip_path)
    _echo(f"[librarian] Published: {_remote.REGISTRY_URL}/registry/{agent_name}@{version}")


@cli.command()
@click.argument("zip_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--key", default="~/.ssh/id_ed25519", show_default=True, help="SSH private key to sign with.")
def sign(zip_file: str, key: str):
    """Sign a wrapped bundle: writes <zip>.sig (SSH signature, namespace agentfactory-unit)."""
    from ..signing import SignatureError, sign_file

    try:
        sig = sign_file(Path(zip_file), Path(key).expanduser())
    except SignatureError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"[librarian] Signature → {sig}")


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
        _echo(f"[librarian] Path not found: {source_path}", err=True)
        sys.exit(1)

    _echo(f"[librarian] Analyzing {source_path}...")
    profile, mapping, all_profiles = Librarian.propose_retrofit(str(source_path))

    _echo(f"[librarian] Detected profile: {profile.upper()}")
    if len(all_profiles) > 1:
        _echo(
            f"[librarian] Warning: multiple profiles matched: {all_profiles}. "
            f"Using '{profile}'; review the proposed mapping below before confirming.",
            err=True,
        )
    _echo("[librarian] Proposed Mapping:")
    for src, dest in mapping.items():
        _echo(f"  - {src} -> {dest}")

    if not yes:
        if not click.confirm("[librarian] Proceed with migration?"):
            _echo("[librarian] Aborted.")
            sys.exit(0)

    # In-place migration
    librarian = Librarian(str(source_path))
    librarian.migrate(mapping)

    # Initialize manifest if missing, otherwise sync
    if not librarian.manifest_path.exists():
        name = source_path.name
        librarian.init(name)

    librarian.sync()

    _echo(f"[librarian] Retrofit complete for '{source_path.name}'.")
    _echo(f"  Standardized into {TRACKED_DIRS}")
