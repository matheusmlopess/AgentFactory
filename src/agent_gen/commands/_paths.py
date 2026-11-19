"""Agent and project path resolution with traversal guards.

Split out of cli.py (#190); `agent_gen.cli` is the entry point and re-exports these names."""

from __future__ import annotations

from pathlib import Path

import click

from ..librarian import (
    HARNESS_ROOT,
    validate_name,
)


def _agent_root(name: str) -> Path:
    try:
        validate_name(name, "agent")
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    new = Path.cwd() / HARNESS_ROOT / "agents" / name
    legacy = Path.cwd() / "agents" / name
    # Backward-compat: fall back to legacy path if .ai/agents/ doesn't exist yet
    if not new.parent.exists() and legacy.parent.exists():
        return legacy
    return new


def _assert_within_root(rel_path: str, root: Path) -> None:
    """Raise ClickException if rel_path resolves outside root (path traversal guard, #59/#S3)."""
    resolved = (root / rel_path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise click.ClickException(f"Path '{rel_path}' resolves outside the agent root — possible path traversal.")


def _assert_valid_project_root(project_root: str) -> Path:
    """Resolve project_root and assert it contains an initialised AgentFactory harness (#143).

    Raises ClickException when:
    - The path resolves outside the filesystem root (traversal guard)
    - The resolved path has no .ai/ subdirectory (not an AgentFactory project)
    """
    path = Path(project_root).resolve()
    ai_root = path / HARNESS_ROOT
    if not ai_root.exists():
        raise click.ClickException(
            f"'{project_root}' is not an AgentFactory project "
            f"(no {HARNESS_ROOT}/ directory found). "
            "Run 'agentfactory-gen init' first."
        )
    return path
