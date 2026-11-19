"""Moving agents and skills in and out: import, import-skill, export.

Split out of cli.py (#190); `agent_gen.cli` is the entry point and re-exports these names."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path

import click

from ..librarian import (
    HARNESS_ROOT,
    MANIFEST_FILE,
    TRACKED_DIRS,
    Librarian,
    _atomic_write_json,
    _inspect_zip,
    validate_name,
)
from . import _remote
from ._group import _echo, cli
from ._paths import _agent_root, _assert_valid_project_root, _assert_within_root
from ._sources import _clone_and_prepare, _find_agent_dir, _normalize_git_url, _verify_publisher_signature


@cli.command("import-skill")
@click.argument("path")
@click.option(
    "--to",
    "target_agent",
    default=".",
    help="Name of the target agent to receive the skill. Defaults to '.' (the root project).",
)
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    help="Root of the project receiving the skill (only used when --to is '.').",
)
def import_skill(path: str, target_agent: str, project_root: str):
    """
    Import a standalone skill into an existing agent or the root project.
    """
    path_obj = Path(path).resolve()
    if not path_obj.exists():
        _echo(f"[librarian] Skill path not found: {path_obj}", err=True)
        sys.exit(1)

    if target_agent == ".":
        # Validate project root is an initialised harness (#143 extension)
        if project_root != ".":
            project_path = _assert_valid_project_root(project_root)
        else:
            project_path = _assert_valid_project_root(".")
        target_root = project_path / HARNESS_ROOT
        _echo(f"[librarian] Importing skill from {path_obj} into root project...")
        try:
            skill_name = Librarian.import_skill_to_project(str(path_obj), str(project_path))
        except (ValueError, FileNotFoundError) as exc:
            _echo(f"[librarian] Skill import failed: {exc}", err=True)
            sys.exit(1)
        _echo(f"[librarian] Successfully imported skill '{skill_name}' into root project.")
        _echo(f"  Path: {target_root / 'skills' / skill_name}")  # .ai/skills/<name>

        Librarian.update_harness_files(str(project_path))
        return

    target_root = _agent_root(target_agent)
    if not target_root.exists():
        _echo(f"[librarian] Target agent '{target_agent}' not found at {target_root}.", err=True)
        sys.exit(1)

    librarian = Librarian(str(target_root))

    try:
        _echo(f"[librarian] Importing skill from {path_obj} into '{target_agent}'...")
        skill_name = librarian.import_skill(str(path_obj))
        _echo(f"[librarian] Successfully imported skill '{skill_name}' into '{target_agent}'.")
        _echo(f"  Path: {target_root / 'skills' / skill_name}")
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        _echo(f"[librarian] Skill import failed: {exc}", err=True)
        sys.exit(1)


@cli.command("import")
@click.argument("zip_path", required=False, default=None)
@click.option(
    "--from-git",
    "from_git",
    default=None,
    metavar="URL",
    help="Git URL to clone, retrofit, and import as an agent (skips ZIP_PATH).",
)
@click.option(
    "--from-registry",
    "from_registry",
    default=None,
    metavar="SLUG",
    help="Registry slug to download and import (e.g. my-agent or my-agent@1.2.0).",
)
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    help="Root of the project receiving the import (for the Handshake).",
)
@click.option(
    "--dry-run",
    "dry_run",
    is_flag=True,
    default=False,
    help="Inspect what would be imported without writing anything to disk (#146).",
)
@click.option(
    "--allow-scripts",
    "allow_scripts",
    is_flag=True,
    default=False,
    help="Skip the interactive scripts review gate (#142).",
)
@click.option(
    "--checksum",
    default=None,
    metavar="FILE",
    help="Path to a .sha256 file to verify the ZIP against before importing (#144).",
)
@click.option(
    "--signature",
    "signature_file",
    default=None,
    metavar="FILE",
    help="SSH signature of the ZIP (from `wrap --sign`); verified before unpacking.",
)
@click.option(
    "--signer",
    default=None,
    metavar="GITHUB_HANDLE",
    help="Who must have signed it; keys come from github.com/<handle>.keys. "
    "Registry imports default to the unit's publisher.",
)
@click.option(
    "--allowed-signers",
    "allowed_signers",
    default=None,
    metavar="FILE",
    help="OpenSSH allowed-signers file to verify against instead of GitHub keys.",
)
@click.option(
    "--require-signature",
    is_flag=True,
    default=False,
    help="Refuse to import a bundle that has no valid publisher signature.",
)
def import_agent(
    zip_path: str,
    from_git: str,
    from_registry: str,
    project_root: str,
    dry_run: bool,
    allow_scripts: bool,
    checksum: str,
    signature_file: str | None,
    signer: str | None,
    allowed_signers: str | None,
    require_signature: bool,
):
    """
    Unpack a portable agent bundle and register it in this project.

    Accepts a local ZIP_PATH, --from-git URL, or --from-registry SLUG.

    Steps (each one can stop the import; temp files are always cleaned up):
      1. Source: resolve the bundle (local ZIP, git clone, registry download + server checksum)
      2. Verify: --checksum and the publisher signature
      3. Inspect: manifest, agent name and executable content, without unpacking
      4. Gate: dry-run preview, or confirm executable content
      5. Install: unpack to a temp dir, audit, record the source, move + register (rolled back on failure)
    """
    sources = [s for s in (zip_path, from_git, from_registry) if s is not None]
    if len(sources) > 1:
        raise click.UsageError("ZIP_PATH, --from-git, and --from-registry are mutually exclusive.")
    if not sources:
        raise click.UsageError("Provide either ZIP_PATH, --from-git URL, or --from-registry SLUG.")
    if project_root != ".":
        _assert_valid_project_root(project_root)  # #143

    bundle, registry_entry, cleanup = _resolve_bundle(zip_path, from_git, from_registry, checksum)
    try:
        _verify_bundle(bundle, checksum, signature_file, signer, allowed_signers, require_signature, registry_entry)
        name, peeked, info = _inspect_bundle(bundle)
        target_root = Path(project_root).resolve() / HARNESS_ROOT / "agents" / name  # #135: not CWD
        if dry_run:
            _print_dry_run(name, peeked, info, target_root)
            return
        _gate_executables(info, allow_scripts)
        if target_root.exists():
            _echo(
                f"[librarian] '{name}' already exists at {target_root}. Remove it first or rename the incoming bundle.",
                err=True,
            )
            sys.exit(1)
        source_ref = {"git": from_git} if from_git else {"registry": from_registry} if from_registry else None
        manifest = _install_bundle(bundle, name, target_root, project_root, source_ref)
    finally:
        cleanup()
    _print_import_summary(name, manifest)


def _resolve_bundle(zip_path, from_git, from_registry, checksum) -> tuple[Path, dict | None, Callable[[], None]]:
    """Step 1: a local ZIP path for the bundle, the registry entry (if any) and an idempotent cleanup."""
    cleanup: Callable[[], None] = lambda: None  # noqa: E731
    registry_entry = None
    if from_git:
        zip_path, cleanup = _clone_and_prepare(from_git)
    if from_registry:
        _echo(f"[librarian] Fetching '{from_registry}' from registry...")
        registry_entry, zip_bytes = _remote._registry_fetch(from_registry)
        fd, tmp_name = tempfile.mkstemp(suffix=".zip")
        with os.fdopen(fd, "wb") as fh:
            fh.write(zip_bytes)
        zip_path = tmp_name

        def cleanup() -> None:
            Path(tmp_name).unlink(missing_ok=True)

        # The registry's own checksum is checked unless the user brings one (#144).
        registry_sha256 = registry_entry.get("sha256")
        if registry_sha256 and not checksum:
            actual = hashlib.sha256(zip_bytes).hexdigest()
            if actual != registry_sha256:
                cleanup()
                _echo(
                    f"[librarian] Registry checksum mismatch — bundle may be tampered.\n"
                    f"  Expected: {registry_sha256}\n"
                    f"  Actual:   {actual}",
                    err=True,
                )
                sys.exit(1)
            _echo("[librarian] Registry checksum auto-verified.")
        elif not registry_sha256 and not checksum:
            # Advisory warning — suppressible with --quiet since it is not a hard failure
            _echo(
                "[librarian] ⚠  Registry did not provide a checksum for this bundle. "
                "Use --checksum <file> to verify provenance manually."
            )
    bundle = Path(zip_path).resolve()
    if not bundle.exists():
        cleanup()
        _echo(f"[librarian] File not found: {bundle}", err=True)
        sys.exit(1)
    return bundle, registry_entry, cleanup


def _verify_bundle(bundle, checksum, signature_file, signer, allowed_signers, require_signature, registry_entry):
    """Step 2: user-supplied checksum, then the publisher signature (#144)."""
    if checksum:
        checksum_path = Path(checksum)
        if not checksum_path.exists():
            _echo(f"[librarian] Checksum file not found: {checksum}", err=True)
            sys.exit(1)
        expected = checksum_path.read_text().strip().split()[0]
        actual = hashlib.sha256(bundle.read_bytes()).hexdigest()
        if actual != expected:
            _echo(
                f"[librarian] Checksum mismatch — ZIP may be tampered.\n  Expected: {expected}\n  Actual:   {actual}",
                err=True,
            )
            sys.exit(1)
        _echo("[librarian] Checksum verified.")
    _verify_publisher_signature(
        bundle, signature_file, signer, allowed_signers, require_signature, registry_entry, None
    )


def _inspect_bundle(bundle: Path) -> tuple[str, dict, dict]:
    """Step 3: (agent name, manifest as shipped, inspection info) — nothing is unpacked (#141 / #146)."""
    info = _inspect_zip(bundle)
    if not info["has_manifest"]:
        _echo("[librarian] Invalid bundle — agent-manifest.json missing from ZIP.", err=True)
        sys.exit(1)
    with zipfile.ZipFile(bundle) as zf, zf.open("agent-manifest.json") as mf:
        peeked = json.load(mf)
    try:
        name = validate_name(peeked.get("name"), "agent")
    except ValueError as exc:
        raise click.ClickException(f"Invalid bundle: {exc}") from exc
    return name, peeked, info


def _print_dry_run(name: str, peeked: dict, info: dict, target_root: Path) -> None:
    """Step 4a: preview only (#140 / #146)."""
    conflict = "YES — would abort" if target_root.exists() else "none"
    _echo("[librarian] DRY RUN — nothing will be written to disk.")
    _echo(f"  Agent   : {name}")
    _echo(f"  Version : {peeked.get('version', 'unknown')}")
    _echo(f"  Target  : {target_root}")
    _echo(f"  Files   : {len(info['names'])}")
    _echo(
        f"  Scripts : {len(info['executable_files'])} file(s)"
        + (f" — {info['executable_files']}" if info["executable_files"] else "")
    )
    _echo(f"  Conflict: {conflict}")


def _gate_executables(info: dict, allow_scripts: bool) -> None:
    """Step 4b: executable content needs --allow-scripts or an explicit yes (#142)."""
    if not info["executable_files"] or allow_scripts:
        return
    _echo(f"[librarian] ⚠  This agent includes {len(info['executable_files'])} executable script(s):")
    for s in info["executable_files"]:
        _echo(f"  {s}")
    _echo("[librarian] Review these files before allowing execution.")
    if not click.confirm("Proceed with import?", default=False):
        _echo("[librarian] Import cancelled.")
        sys.exit(0)


def _install_bundle(bundle: Path, name: str, target_root: Path, project_root: str, source_ref: dict | None) -> dict:
    """Step 5: unpack + audit in a temp dir, record the source, then move and register as one unit (#146)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir) / name
        temp_root.mkdir(parents=True)

        _echo(f"[librarian] Unpacking '{name}'...")
        manifest = Librarian.unpack(str(bundle), str(temp_root))

        _echo(f"[librarian] Auditing '{name}' before registration...")
        report = Librarian(str(temp_root)).audit()
        if report["broken_resources"] or report["broken_dependencies"] or report.get("invalid_skill_manifests"):
            _echo("[librarian] Audit FAILED for imported bundle. Aborting...", err=True)
            sys.exit(1)

        # Record where the agent came from (for `export`) while it is still staged, so the project only ever
        # sees a complete agent.
        if source_ref:
            staged_manifest = temp_root / MANIFEST_FILE
            try:
                data = json.loads(staged_manifest.read_text())
                data["source"] = source_ref
                _atomic_write_json(staged_manifest, data)
                manifest["source"] = source_ref
            except (OSError, ValueError):
                pass  # non-fatal: export can still take --git explicitly

        target_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(temp_root), str(target_root))
        _echo(f"[librarian] Registering '{name}' in project manifest...")
        try:
            Librarian.register_in_project(manifest, project_root)
        except Exception as exc:  # any failure rolls the move back; the cause is chained
            shutil.rmtree(target_root, ignore_errors=True)
            with contextlib.suppress(Exception):
                Librarian.deregister_from_project(name, project_root)
            raise click.ClickException(
                f"Registration failed, import rolled back (nothing was left in {target_root.parent}): {exc}"
            ) from exc
    return manifest


def _print_import_summary(name: str, manifest: dict) -> None:
    """Paste-ready summary of what was added."""
    res = manifest["resources"]
    docs = res.get("docs", [])
    _echo("")
    _echo("=" * 60)
    _echo("Librarian: Import Complete.")
    _echo(
        f"  Added {len(res.get('skills', []))} skill(s), {len(res.get('commands', []))} command(s), "
        f"{len(docs)} doc(s), {len(res.get('scripts', []))} script(s), "
        f"and {len(res.get('orchestration', []))} orchestration file(s) to your environment."
    )
    _echo(f"  You are now configured as the '{name}' agent.")
    claude_md = next((d for d in docs if "CLAUDE.md" in d), None)
    if claude_md:
        _echo(f"  Check {claude_md} for your new instructions.")
    _echo("=" * 60)


@cli.command("export")
@click.argument("name")
@click.option(
    "--git",
    "git_url",
    default=None,
    metavar="URL",
    help="Source repo to patch (default: the agent's recorded source from import).",
)
@click.option(
    "--subpath",
    default=None,
    help="Path inside the source repo where the agent lives (default: auto-detect).",
)
@click.option(
    "--branch",
    "branch_name",
    default=None,
    help="Branch to create & push (default: agentfactory/export-<name>).",
)
@click.option("-m", "--message", "message", default=None, help="Commit message.")
@click.option("--project-root", default=".", show_default=True, help="Project root holding the agent.")
@click.option("--push/--no-push", default=True, help="Push the branch to the source remote.")
@click.option("--pr/--no-pr", default=True, help="Open a PR with gh (requires --push).")
def export_agent(name, git_url, subpath, branch_name, message, project_root, push, pr):
    """
    Patch a locally-modified agent back to its source-of-truth git repo.

    Clones the source, copies this project's agents/<NAME>/ over the agent's
    location in the source, commits on a new branch, pushes, and opens a PR —
    so edits made to an imported agent flow back upstream.
    """
    project_path = Path(project_root).resolve()
    agent_root = project_path / HARNESS_ROOT / "agents" / name
    if not agent_root.is_dir():
        raise click.ClickException(f"Agent '{name}' not found at {agent_root}.")

    manifest_path = agent_root / MANIFEST_FILE
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except ValueError:
            manifest = {}

    src = git_url or (manifest.get("source") or {}).get("git")
    if not src:
        raise click.ClickException(
            f"No source repo recorded for '{name}'. Pass --git URL "
            "(this agent was imported from a ZIP/registry or deployed locally)."
        )
    src = _normalize_git_url(src)

    branch_name = branch_name or f"agentfactory/export-{name}"
    message = message or f"agent({name}): sync from AgentFactory export"

    if subpath and ".." in Path(subpath).parts:
        raise click.ClickException(f"--subpath '{subpath}' must not contain '..'.")

    tmp_dir = tempfile.mkdtemp(prefix="agentfactory_export_")
    clone_dir = os.path.join(tmp_dir, "src")

    def _git(*args, check=True):
        proc = subprocess.run(["git", "-C", clone_dir, *args], capture_output=True, text=True)
        if check and proc.returncode != 0:
            raise click.ClickException(f"git {' '.join(args)} failed:\n{proc.stderr.strip()}")
        return proc

    try:
        _echo(f"[librarian] Cloning {src} ...")
        clone = subprocess.run(["git", "clone", "--quiet", src, clone_dir], capture_output=True, text=True)
        if clone.returncode != 0:
            raise click.ClickException(f"git clone failed:\n{clone.stderr.strip()}")
        clone_path = Path(clone_dir)

        # Detect where the agent lives in the source repo (same rule as `import --from-git`).
        if subpath is None:
            found = _find_agent_dir(clone_path)
            if found is None:
                subpath = "agent"
            else:
                rel = found.relative_to(clone_path).as_posix()
                subpath = "" if rel == "." else rel
        dest = clone_path / subpath if subpath else clone_path
        _assert_within_root(subpath or ".", clone_path)
        dest.mkdir(parents=True, exist_ok=True)

        # Apply the local agent (manifest + tracked resource dirs) over the source.
        _echo(f"[librarian] Applying '{name}' → {subpath or '<repo root>'} ...")
        if manifest_path.exists():
            shutil.copy2(manifest_path, dest / MANIFEST_FILE)
        for d in TRACKED_DIRS:
            src_d = agent_root / d
            if src_d.is_dir():
                dst_d = dest / d
                if dst_d.exists():
                    shutil.rmtree(dst_d)
                shutil.copytree(src_d, dst_d)

        _git("checkout", "-b", branch_name)
        _git("add", "-A")
        if not _git("status", "--porcelain").stdout.strip():
            _echo("[librarian] No changes to export — the source already matches. ✓")
            return
        _git(
            "-c",
            "user.email=agentfactory@local",
            "-c",
            "user.name=AgentFactory",
            "commit",
            "-m",
            message,
        )
        _echo("[librarian] Committed: " + _git("--no-pager", "log", "-1", "--oneline").stdout.strip())

        if not push:
            patch_file = project_path / f"{name}-export.patch"
            patch_file.write_text(_git("--no-pager", "format-patch", "-1", "--stdout").stdout)
            _echo(f"[librarian] --no-push: patch written to {patch_file}")
            _echo(f"  apply upstream with:  git checkout -b {branch_name} && git am {patch_file.name}")
            return

        _echo(f"[librarian] Pushing '{branch_name}' to origin ...")
        _git("push", "-u", "origin", branch_name)

        if pr:
            pr_proc = subprocess.run(
                [
                    "gh",
                    "pr",
                    "create",
                    "--head",
                    branch_name,
                    "--title",
                    message,
                    "--body",
                    f"Automated export of agent `{name}` from AgentFactory.",
                ],
                cwd=clone_dir,
                capture_output=True,
                text=True,
            )
            if pr_proc.returncode == 0:
                _echo(f"[librarian] PR opened: {pr_proc.stdout.strip()}")
            else:
                _echo(
                    f"[librarian] Pushed '{branch_name}'; open a PR manually (gh: {pr_proc.stderr.strip()})", err=True
                )
        else:
            _echo(f"[librarian] Pushed '{branch_name}'. Open a PR from it when ready.")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
