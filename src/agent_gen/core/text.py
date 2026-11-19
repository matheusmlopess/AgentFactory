"""Small text and git helpers used when reading source repos and manifests.

Split out of librarian.py (#189); `agent_gen.librarian` re-exports the public names."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _extract_first_paragraph(path: Path) -> str:
    """
    Extract the first meaningful paragraph from a Markdown file.
    Skips YAML frontmatter (--- blocks), blank lines, and # headers.
    Returns up to 200 chars of the first descriptive sentence/paragraph.
    """
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        collect = []
        i = 0
        # Skip YAML frontmatter
        if lines and lines[0].strip() == "---":
            i = 1
            while i < len(lines):
                if lines[i].strip() == "---":
                    i += 1
                    break
                i += 1
        # Collect first non-header, non-empty, non-comment paragraph
        for line in lines[i:]:
            stripped = line.strip()
            if not stripped:
                if collect:
                    break
                continue
            if stripped.startswith("#"):
                if collect:
                    break
                continue
            # Skip HTML comments (<!-- ... -->)
            if stripped.startswith("<!--"):
                continue
            collect.append(stripped)
            if len(" ".join(collect)) >= 200:
                break
        text = " ".join(collect).strip()
        return text[:200] if text else ""
    except Exception:
        return ""


def _git_ref(path: str) -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=path,
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        return "untracked"
