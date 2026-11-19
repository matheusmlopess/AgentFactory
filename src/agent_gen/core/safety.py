"""Untrusted-input guards: ZIP extraction, names, Markdown sanitizing, atomic JSON writes, bundle inspection.

Split out of librarian.py (#189); `agent_gen.librarian` re-exports the public names."""

from __future__ import annotations

import json
import logging
import os
import re
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)


def _safe_extract(zf: zipfile.ZipFile, target_dir: Path) -> None:
    """Extract ZIP members, rejecting any that would escape target_dir (zip-slip guard)."""
    target_resolved = target_dir.resolve()
    for member in zf.infolist():
        dest = (target_dir / member.filename).resolve()
        if dest != target_resolved and not str(dest).startswith(str(target_resolved) + os.sep):
            raise ValueError(f"Unsafe ZIP entry '{member.filename}' — zip slip attack blocked.")
        zf.extract(member, target_dir)


# Agent and skill names become directory names under .ai/agents/ and skills/.
# They come from untrusted sources (bundle manifests, SKILL.md frontmatter, CLI args),
# so they must never carry path separators, "..", or absolute paths.
_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


def validate_name(name: object, kind: str = "agent") -> str:
    """Return *name* if it is a safe single path component, else raise ValueError."""
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name) or ".." in name:
        raise ValueError(
            f"Invalid {kind} name {name!r}: use 1-64 letters, digits, '.', '_' or '-', starting with a letter or digit."
        )
    return name


def safe_child(base: Path, name: object, kind: str = "agent") -> Path:
    """Join a validated *name* onto *base* and confirm the result stays inside *base*."""
    child = base / validate_name(name, kind)
    if not child.resolve().is_relative_to(base.resolve()):
        raise ValueError(f"{kind} name {name!r} resolves outside {base}")
    return child


def _sanitize_for_markdown(text: object) -> str:
    """
    Strip prompt-injection vectors before embedding text in AI-readable markdown.

    Removes HTML comments (used as AI instruction markers), flattens newlines
    (prevents multi-line injection), and caps length at 200 chars.
    """
    if not isinstance(text, str):
        text = str(text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)  # strip HTML comments
    text = " ".join(text.splitlines())  # flatten newlines
    text = re.sub(r"\s+", " ", text).strip()
    return text[:200]


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON to *path* atomically via a temp-file + os.replace().

    On POSIX, os.replace() is a single syscall (rename), so a concurrent reader
    always sees either the old or the new file, never a partial write.  The temp
    file is cleaned up on any error so it never sits alongside the real file.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except BaseException:  # clean up on any failure (incl. KeyboardInterrupt), then re-raise
        tmp.unlink(missing_ok=True)
        raise


def _workflow_has_shell_steps(raw: bytes) -> bool:
    """True when a .workflow.json declares any shell step (or cannot be parsed: assume yes)."""
    try:
        data = json.loads(raw.decode("utf-8"))
        return any(
            isinstance(step, dict) and step.get("type", "shell") == "shell"  # models.py default
            for step in data.get("steps", [])
        )
    except (ValueError, AttributeError, UnicodeDecodeError):
        return True


def _inspect_zip(zip_path: Path) -> dict:
    """Inspect a ZIP's contents without extracting anything to disk.

    Returns:
        has_manifest     — bool, agent-manifest.json present at root
        names            — list of all member filenames
        scripts          — list of members under scripts/ that are files (path-prefix)
        executable_files — scripts/ members + shebang-detected files in commands/ and orchestration/
                           + orchestration workflows that declare shell steps
        structure_ok     — bool, has agent-manifest.json + at least one tracked dir
    """
    _SHEBANG_DIRS = frozenset(("commands", "orchestration"))
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        shebang_files: list[str] = []
        for n in names:
            if n.endswith("/"):
                continue
            prefix = n.split("/")[0]
            if prefix in _SHEBANG_DIRS:
                try:
                    with zf.open(n) as member:
                        head = member.read(2)
                        if head == b"#!":
                            shebang_files.append(n)
                        elif n.endswith(".workflow.json") and _workflow_has_shell_steps(head + member.read()):
                            # Workflow shell steps run through `orchestrate run` (shell=True).
                            shebang_files.append(n)
                except (OSError, zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
                    # A member we cannot read cannot be shown to be harmless: gate it like a script.
                    logger.warning("cannot inspect %s in %s (%s); treating it as executable", n, zip_path, exc)
                    shebang_files.append(n)
    scripts = [n for n in names if n.startswith("scripts/") and not n.endswith("/")]
    executable_files = scripts + shebang_files
    has_manifest = "agent-manifest.json" in names
    tracked_dirs_found = any(
        any(n.startswith(d + "/") for n in names) for d in ["skills", "commands", "docs", "scripts", "orchestration"]
    )
    return {
        "has_manifest": has_manifest,
        "names": names,
        "scripts": scripts,
        "executable_files": executable_files,
        "structure_ok": has_manifest and tracked_dirs_found,
    }
