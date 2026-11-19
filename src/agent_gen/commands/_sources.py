"""Where bundles come from: git clones, declared agent dirs, publisher signatures.

Split out of cli.py (#190); `agent_gen.cli` is the entry point and re-exports these names."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

import click

from ..librarian import (
    MANIFEST_FILE,
    Librarian,
)
from ._group import _echo


def _find_agent_dir(repo: Path) -> Path | None:
    """Where a repo already ships an AgentFactory Portable Unit: `agent/` or the repo root.

    Only a manifest with `name` and `resources` counts (a project's `.ai/agent-manifest.json` is a registry,
    not a unit, and lives elsewhere).
    """
    for candidate in (repo / "agent", repo):
        manifest = candidate / MANIFEST_FILE
        if manifest.is_file():
            try:
                data = json.loads(manifest.read_text())
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and data.get("name") and isinstance(data.get("resources"), dict):
                return candidate
    return None


def _clone_and_prepare(url: str) -> tuple[str, Callable[[], None]]:
    """
    Clone a git URL, retrofit it to AgentFactory standard, and wrap it as a ZIP.

    Returns:
        (zip_path_str, cleanup_fn) — caller must call cleanup_fn() after import.
    """
    # A local checkout is accepted as a file:// URL (#179 gap 2).
    local = Path(url).expanduser()
    if "://" not in url and not url.startswith("git@") and local.is_dir():
        url = local.resolve().as_uri()

    # Derive agent name from URL and sanitize (#S4)
    name = url.rstrip("/").split("/")[-1]
    name = name.removesuffix(".git")
    name = re.sub(r"[^\w\-]", "-", name).strip("-")
    if not name:
        raise click.ClickException("Could not derive a valid agent name from the URL.")

    tmp_dir = tempfile.mkdtemp(prefix="agentfactory_import_")
    cloned_dir = os.path.join(tmp_dir, name)

    try:
        # Validate URL scheme before passing to subprocess (#58)
        allowed_schemes = ("https://", "http://", "git@", "ssh://", "git://", "file://")
        if not any(url.startswith(s) for s in allowed_schemes):
            raise click.ClickException(
                f"Invalid git URL '{url}'. Must start with one of: {', '.join(allowed_schemes)}"
                " (or be an existing local directory)"
            )

        _echo(f"[librarian] Cloning {url} ...")
        result = subprocess.run(
            ["git", "clone", "--quiet", url, cloned_dir],  # --quiet flag (#53)
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise click.ClickException(f"git clone failed:\n{result.stderr.strip()}")

        # 0. The repo already ships a Portable Unit: wrap it exactly as declared (#179 gap 1).
        agent_dir = _find_agent_dir(Path(cloned_dir))
        if agent_dir is not None:
            rel = agent_dir.relative_to(cloned_dir).as_posix()
            _echo(
                f"[librarian] Found agent manifest at {rel if rel != '.' else '<repo root>'}/ — importing it as declared ..."
            )
            try:
                zip_path = Librarian(str(agent_dir)).wrap(tmp_dir)
            except FileNotFoundError as exc:
                raise click.ClickException(f"The repo's agent manifest is incomplete: {exc}") from exc

            def _cleanup_declared():
                shutil.rmtree(tmp_dir, ignore_errors=True)

            return str(zip_path), _cleanup_declared

        # 1. Extract context from source BEFORE retrofit
        _echo("[librarian] Extracting context from source docs ...")
        context = Librarian._extract_source_context(cloned_dir)

        # 2. Retrofit if needed
        profile, mapping, _ = Librarian.propose_retrofit(cloned_dir)
        if mapping:
            _echo(f"[librarian] Retrofitting (profile: {profile}) ...")
            Librarian(cloned_dir).migrate(mapping)

        # 3. Promote sub-agent .md files and create skill-manifest.json stubs
        _echo("[librarian] Generating skill manifests ...")
        Librarian._auto_stub_skill_manifests(cloned_dir, context)

        # 4. Init + patch manifest description + sync resources
        _echo("[librarian] Initialising agent manifest ...")
        Librarian._auto_init_agent_manifest(cloned_dir, name, context)

        # 5. Wrap into a ZIP
        _echo("[librarian] Wrapping into portable unit ...")
        zip_path = Librarian(cloned_dir).wrap(tmp_dir)

        def _cleanup():
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return str(zip_path), _cleanup

    except click.ClickException:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise click.ClickException(f"Preparation failed: {exc}") from exc


def _normalize_git_url(url: str) -> str:
    """
    Accept a remote URL (https/http/git@/ssh/git:///file://) or a local path.

    An existing local path is converted to an absolute ``file://`` URL so the same
    code path works for remotes, local clones, and tests.
    """
    remote_schemes = ("https://", "http://", "git@", "ssh://", "git://", "file://")
    if url.startswith(remote_schemes):
        return url
    p = Path(url).expanduser()
    if p.exists():
        return p.resolve().as_uri()
    raise click.ClickException(
        f"Invalid git target '{url}'. Use a URL ({', '.join(remote_schemes)}) or an existing local path."
    )


def _verify_publisher_signature(
    zip_path, signature_file, signer, allowed_signers, require_signature, registry_entry, cleanup
) -> None:
    """Check the bundle's SSH signature when one is available or required; exit 1 on failure."""
    from ..signing import SignatureError, github_allowed_signers, verify_file

    def fail(msg: str) -> None:
        if cleanup:
            cleanup()
        _echo(f"[librarian] {msg}", err=True)
        sys.exit(1)

    signature = None
    if signature_file:
        sig_path = Path(signature_file)
        if not sig_path.is_file():
            fail(f"Signature file not found: {signature_file}")
        signature = sig_path.read_text()
    elif registry_entry and registry_entry.get("signature"):
        signature = registry_entry["signature"]
    elif zip_path and Path(f"{zip_path}.sig").is_file() and (signer or allowed_signers or require_signature):
        signature = Path(f"{zip_path}.sig").read_text()

    if signature is None:
        if require_signature:
            fail("No publisher signature for this bundle (--require-signature).")
        return

    identity = signer or (registry_entry or {}).get("owner")
    try:
        if allowed_signers:
            signers_text = Path(allowed_signers).read_text()
            identity = identity or "agentfactory"
        elif identity:
            signers_text = github_allowed_signers(identity)
        else:
            fail("Signature given but no signer: pass --signer <github-handle> or --allowed-signers <file>.")
            return
        verify_file(Path(zip_path), signature, identity, signers_text)
    except (SignatureError, OSError) as exc:
        fail(f"Publisher signature check failed — do not trust this bundle.\n  {exc}")
    _echo(f"[librarian] Publisher signature verified ({identity}).")
