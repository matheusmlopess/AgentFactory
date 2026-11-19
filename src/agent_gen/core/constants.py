"""Harness layout constants shared by every core module.

Split out of librarian.py (#189); `agent_gen.librarian` re-exports the public names."""

from __future__ import annotations

TRACKED_DIRS = ["skills", "commands", "docs", "scripts", "orchestration"]


MANIFEST_FILE = "agent-manifest.json"


HARNESS_ROOT = ".ai"


CONTEXT_FILE = "AgentFactory.md"  # single source of truth for all CLI instructions
