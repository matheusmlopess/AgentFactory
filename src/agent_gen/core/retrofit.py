"""Retrofit foreign agent layouts (Claude/Codex/Gemini/agy) into the AgentFactory standard.

Split out of librarian.py (#189); `agent_gen.librarian` re-exports the public names."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import shutil
from pathlib import Path

from .base import LibrarianBase
from .constants import TRACKED_DIRS
from .text import _extract_first_paragraph

logger = logging.getLogger(__name__)

CONVERSION_PROFILES = {
    "claude": {
        ".claude/skills": "skills",
        ".claude/commands": "commands",
        "CLAUDE.md": "docs/CLAUDE.md",
        ".claude/rules": "docs/rules",
        ".claude/templates": "docs/templates",
        ".claude/output-styles": "docs/output-styles",
        ".claude/tools": "scripts/tools",
        ".claude/workflows": "orchestration/workflows",
        ".claude/agents": "orchestration/agents",
        "AGENTS.md": "orchestration/AGENTS.md",
    },
    # Legacy Gemini CLI layout (retired 2026-06-18) — kept so old projects still retrofit
    "gemini": {
        ".gemini/skills": "skills",
        ".gemini/extensions": "skills/extensions",
        "GEMINI.md": "docs/GEMINI.md",
        "AGENTS.md": "orchestration/AGENTS.md",
    },
    # Antigravity CLI (agy) — successor to Gemini CLI, open-standard .agents/ layout
    "antigravity": {
        ".agents/skills": "skills",
        ".agents/rules": "docs/rules",
        ".agents/workflows": "orchestration/workflows",
        "GEMINI.md": "docs/GEMINI.md",
        "AGENTS.md": "orchestration/AGENTS.md",
    },
    "codex": {
        ".codex/prompts": "skills/prompts",
        "codex.md": "docs/codex.md",
        ".codex/templates": "docs/templates",
        ".codex/workflows": "orchestration/workflows",
        "AGENTS.md": "orchestration/AGENTS.md",
    },
}


def _librarian():
    """The composed Librarian class (late import: it is built from these mixins)."""
    from ..librarian import Librarian

    return Librarian


class RetrofitMixin(LibrarianBase):
    """Retrofit foreign agent layouts (Claude/Codex/Gemini/agy) into the AgentFactory standard."""

    @classmethod
    def propose_retrofit(cls, source_dir: str) -> tuple[str, dict[str, str], list[str]]:
        """
        Analyze a directory and propose a mapping to AgentFactory standard.
        Returns (profile_name, mapping, all_matching_profiles).
        all_matching_profiles has >1 entry when multiple profiles matched (#44).
        """
        source_path = Path(source_dir).resolve()
        detected_profile = "auto"
        mapping: dict[str, str] = {}
        all_matching_profiles: list[str] = []

        # Heuristic profile detection — collect ALL matches (#44)
        for profile, rules in CONVERSION_PROFILES.items():
            matches = sum(1 for trigger in rules if (source_path / trigger).exists())
            if matches >= 1:
                all_matching_profiles.append(profile)

        if all_matching_profiles:
            detected_profile = all_matching_profiles[0]

        # Build mapping based on detected profile or auto
        rules = CONVERSION_PROFILES.get(detected_profile, {})

        # Add profile-specific rules
        mapping.update({src: dest for src, dest in rules.items() if (source_path / src).exists()})

        # Add auto-rules for common patterns if not already mapped
        auto_rules = {
            "skills": "skills",
            "commands": "commands",
            "docs": "docs",
            "scripts": "scripts",
            "src": "scripts",
            "orchestration": "orchestration",
        }
        for src, dest in auto_rules.items():
            if src not in mapping and (source_path / src).exists():
                mapping[src] = dest

        return detected_profile, mapping, all_matching_profiles

    def migrate(self, mapping: dict[str, str]) -> None:
        """
        Execute the migration based on a mapping with a safe rollback mechanism.
        """
        import shutil
        import tempfile

        # Use a temporary staging area to prevent corrupting the original directory on failure
        with tempfile.TemporaryDirectory() as staging_dir:
            staging_path = Path(staging_dir) / self.agent_root.name

            # Copy source to staging
            shutil.copytree(self.agent_root, staging_path)

            try:
                # 1. Create standard directories in staging
                for d in TRACKED_DIRS:
                    (staging_path / d).mkdir(parents=True, exist_ok=True)
                    (staging_path / d / ".gitkeep").touch()

                # 2. Move files according to mapping in staging
                for src_rel, dest_rel in mapping.items():
                    src_path = staging_path / src_rel
                    if not src_path.exists():
                        continue

                    dest_path = staging_path / dest_rel

                    if src_path.is_dir():
                        # If destination is also a directory, merge contents
                        for item in src_path.iterdir():
                            target = dest_path / item.name
                            target.parent.mkdir(parents=True, exist_ok=True)
                            if target.exists() and target.is_dir() and item.is_dir():
                                # Simple recursive merge if both are dirs
                                for subitem in item.iterdir():
                                    sub_target = target / subitem.name
                                    sub_target.parent.mkdir(parents=True, exist_ok=True)
                                    shutil.move(str(subitem), str(sub_target))
                                item.rmdir()
                            else:
                                shutil.move(str(item), str(target))
                        with contextlib.suppress(OSError):  # directory not empty or already moved
                            src_path.rmdir()
                    else:
                        # If destination is a directory, move file into it
                        if dest_rel in TRACKED_DIRS:
                            shutil.move(str(src_path), str(dest_path / src_path.name))
                        else:
                            # Specific file-to-file mapping
                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.move(str(src_path), str(dest_path))

            except Exception as exc:
                # Nothing outside the staging copy has been touched yet.
                raise RuntimeError(f"Migration failed and was safely rolled back. Reason: {exc}") from exc

            # 3. Swap: move the original aside, move staging in, then drop the original.
            # If the move-in fails, the original is put back, so the agent is never lost.
            backup = self.agent_root.with_name(f".{self.agent_root.name}.pre-migrate")
            if backup.exists():
                shutil.rmtree(backup)
            os.replace(self.agent_root, backup)
            try:
                shutil.move(str(staging_path), str(self.agent_root))
            except Exception as exc:
                if self.agent_root.exists():
                    shutil.rmtree(self.agent_root, ignore_errors=True)
                os.replace(backup, self.agent_root)
                raise RuntimeError(f"Migration failed and was safely rolled back. Reason: {exc}") from exc
            shutil.rmtree(backup, ignore_errors=True)

    @staticmethod
    def _extract_source_context(source_dir: str) -> dict:
        """
        Read CLAUDE.md, AGENTS.md, and .claude/agents/*.md from a raw repo
        BEFORE retrofit to extract agent and sub-agent descriptions.

        Returns:
            {"description": str, "agents": {name: str}}
        """
        root = Path(source_dir).resolve()
        ctx: dict = {"description": "", "agents": {}}

        # Agent-level description: README is the most reliable source for a project
        # description; CLAUDE.md / AGENTS.md often contain instructions, not descriptions.
        for candidate in ["README.md", "CLAUDE.md", "AGENTS.md", ".ai/AgentFactory.md"]:
            f = root / candidate
            if f.exists():
                desc = _extract_first_paragraph(f)
                if desc:
                    ctx["description"] = desc
                    break

        # Sub-agent descriptions from .claude/agents/*.md
        agents_dir = root / ".claude" / "agents"
        if agents_dir.exists():
            for md in sorted(agents_dir.glob("*.md")):
                desc = _extract_first_paragraph(md)
                ctx["agents"][md.stem] = desc

        return ctx

    @staticmethod
    def _auto_init_agent_manifest(agent_dir: str, name: str, context: dict) -> None:
        """
        Create agent-manifest.json (via init()) if missing, patch description
        from extracted context, then sync resources from disk.
        """
        lib = _librarian()(agent_dir)
        if not lib.manifest_path.exists():
            lib.init(name)
        if context.get("description"):
            manifest = lib._load_manifest()
            manifest["description"] = context["description"][:200]
            lib._save_manifest(manifest)
        lib.sync()

    @staticmethod
    def _auto_stub_skill_manifests(agent_dir: str, context: dict) -> None:
        """
        After retrofit, scan orchestration/agents/ and skills/ for flat .md files
        without a skill-manifest.json. For each, promote it to a subdirectory and
        create a skill-manifest.json stub with description from extracted context.
        """
        root = Path(agent_dir).resolve()
        scan_dirs = [root / "orchestration" / "agents", root / "skills"]
        for scan_dir in scan_dirs:
            if not scan_dir.exists():
                continue
            # Snapshot list before we start moving files
            md_files = list(scan_dir.glob("*.md"))
            for md_file in md_files:
                stem = md_file.stem
                # Promote flat .md into a named subdirectory
                skill_dir = scan_dir / stem
                skill_dir.mkdir(exist_ok=True)
                dest_md = skill_dir / md_file.name
                if not dest_md.exists():
                    shutil.move(str(md_file), str(dest_md))
                elif md_file.exists():
                    md_file.unlink()
                # Create skill-manifest.json stub if missing
                sm_path = skill_dir / "skill-manifest.json"
                if not sm_path.exists():
                    desc = context["agents"].get(stem, "") or _extract_first_paragraph(dest_md) or f"{stem} sub-agent"
                    sm_path.write_text(
                        json.dumps(
                            {
                                "name": stem,
                                "version": "1.0.0",
                                "description": desc[:200],
                            },
                            indent=2,
                        )
                    )
