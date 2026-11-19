"""Moving agents and skills in and out: import, import-skill, export.

Split out of cli.py (#190); `agent_gen.cli` is the entry point and re-exports these names."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
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
    except Exception as exc:
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

    Steps:
      1. Pre-unpack inspection (structure, scripts, checksum)
      2. Unpack ZIP to temp dir
      3. Audit unpacked content
      4. Move to final location + register in project manifest
    """
    import hashlib

    _cleanup = None

    registry_entry: dict | None = None
    sources = [s for s in (zip_path, from_git, from_registry) if s is not None]
    if len(sources) > 1:
        raise click.UsageError("ZIP_PATH, --from-git, and --from-registry are mutually exclusive.")
    if not sources:
        raise click.UsageError("Provide either ZIP_PATH, --from-git URL, or --from-registry SLUG.")

    # Validate project root is an initialised harness (#143)
    if project_root != ".":
        _assert_valid_project_root(project_root)

    if from_git:
        zip_path, _cleanup = _clone_and_prepare(from_git)

    if from_registry:
        _echo(f"[librarian] Fetching '{from_registry}' from registry...")
        _entry, zip_bytes = _remote._registry_fetch(from_registry)
        registry_entry = _entry
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        tmp.write(zip_bytes)
        tmp.close()
        zip_path = tmp.name
        _cleanup = lambda p=tmp.name: os.unlink(p)  # noqa: E731

        # Auto-verify if registry provides a checksum (#144 extension)
        registry_sha256 = _entry.get("sha256")
        if registry_sha256 and not checksum:
            actual = hashlib.sha256(zip_bytes).hexdigest()
            if actual != registry_sha256:
                if _cleanup:
                    _cleanup()
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

    zip_path = Path(zip_path).resolve()

    if not zip_path.exists():
        _echo(f"[librarian] File not found: {zip_path}", err=True)
        sys.exit(1)

    # --- Checksum verification (#144) ---
    if checksum:
        checksum_path = Path(checksum)
        if not checksum_path.exists():
            _echo(f"[librarian] Checksum file not found: {checksum}", err=True)
            sys.exit(1)
        expected = checksum_path.read_text().strip().split()[0]
        actual = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        if actual != expected:
            _echo(
                f"[librarian] Checksum mismatch — ZIP may be tampered.\n  Expected: {expected}\n  Actual:   {actual}",
                err=True,
            )
            sys.exit(1)
        _echo("[librarian] Checksum verified.")

    # --- Publisher signature (#144) ---
    _verify_publisher_signature(
        zip_path,
        signature_file,
        signer,
        allowed_signers,
        require_signature,
        registry_entry,
        _cleanup,
    )

    # --- Pre-unpack inspection (#141 / #146) ---
    info = _inspect_zip(zip_path)
    if not info["has_manifest"]:
        _echo("[librarian] Invalid bundle — agent-manifest.json missing from ZIP.", err=True)
        sys.exit(1)

    # Peek at the archive to get the agent name before unpacking
    with zipfile.ZipFile(zip_path) as zf, zf.open("agent-manifest.json") as mf:
        peeked = json.load(mf)

    try:
        name = validate_name(peeked.get("name"), "agent")
    except ValueError as exc:
        if _cleanup:
            _cleanup()
        raise click.ClickException(f"Invalid bundle: {exc}") from exc
    # Resolve target_root against project_root, not CWD (#135)
    project_path = Path(project_root).resolve()
    target_root = project_path / HARNESS_ROOT / "agents" / name

    # --- Dry-run: print preview and exit (#140 / #146) ---
    if dry_run:
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
        if _cleanup:
            _cleanup()
        sys.exit(0)

    # --- Scripts gate (#142 + shebang extension) ---
    if info["executable_files"] and not allow_scripts:
        _echo(f"[librarian] ⚠  This agent includes {len(info['executable_files'])} executable script(s):")
        for s in info["executable_files"]:
            _echo(f"  {s}")
        _echo("[librarian] Review these files before allowing execution.")
        if not click.confirm("Proceed with import?", default=False):
            _echo("[librarian] Import cancelled.")
            if _cleanup:
                _cleanup()
            sys.exit(0)

    if target_root.exists():
        _echo(
            f"[librarian] '{name}' already exists at {target_root}. Remove it first or rename the incoming bundle.",
            err=True,
        )
        sys.exit(1)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir) / name
        temp_root.mkdir(parents=True)

        _echo(f"[librarian] Unpacking '{name}'...")
        manifest = Librarian.unpack(str(zip_path), str(temp_root))

        # Deep Audit before finalizing
        _echo(f"[librarian] Auditing '{name}' before registration...")
        librarian = Librarian(str(temp_root))
        report = librarian.audit()
        if report["broken_resources"] or report["broken_dependencies"] or report.get("invalid_skill_manifests"):
            _echo("[librarian] Audit FAILED for imported bundle. Aborting...", err=True)
            if _cleanup:
                _cleanup()
            sys.exit(1)

        # Record where this agent came from (so `export` can patch changes back to it) while the
        # bundle is still in the temp dir, so the project only ever sees a complete agent.
        source_ref = None
        if from_git:
            source_ref = {"git": from_git}
        elif from_registry:
            source_ref = {"registry": from_registry}
        if source_ref:
            staged_manifest = temp_root / MANIFEST_FILE
            try:
                data = json.loads(staged_manifest.read_text())
                data["source"] = source_ref
                _atomic_write_json(staged_manifest, data)
                manifest["source"] = source_ref
            except (OSError, ValueError):
                pass  # non-fatal: export can still take --git explicitly

        # Move into place and register as one unit: if registration fails, undo the move (#146).
        target_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(temp_root), str(target_root))
        _echo(f"[librarian] Registering '{name}' in project manifest...")
        try:
            Librarian.register_in_project(manifest, project_root)
        except Exception as exc:
            shutil.rmtree(target_root, ignore_errors=True)
            try:
                Librarian.deregister_from_project(name, project_root)
            except Exception:
                pass
            if _cleanup:
                _cleanup()
            raise click.ClickException(
                f"Registration failed, import rolled back (nothing was left in {target_root.parent}): {exc}"
            ) from exc

    # Clean up temp dir from --from-git clone
    if _cleanup:
        _cleanup()

    # Success summary (paste-ready for Claude)
    skills = manifest["resources"].get("skills", [])
    commands = manifest["resources"].get("commands", [])
    docs = manifest["resources"].get("docs", [])
    scripts = manifest["resources"].get("scripts", [])
    orchestration = manifest["resources"].get("orchestration", [])

    _echo("")
    _echo("=" * 60)
    _echo("Librarian: Import Complete.")
    _echo(
        f"  Added {len(skills)} skill(s), {len(commands)} command(s), "
        f"{len(docs)} doc(s), {len(scripts)} script(s), "
        f"and {len(orchestration)} orchestration file(s) to your environment."
    )
    _echo(f"  You are now configured as the '{name}' agent.")
    if docs:
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
