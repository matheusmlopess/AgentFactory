"""SKILL.md parsing/reconciliation and skill imports (agent-level and project-level).

Split out of librarian.py (#189); `agent_gen.librarian` re-exports the public names."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path

from .base import LibrarianBase
from .constants import HARNESS_ROOT
from .safety import _atomic_write_json, _safe_extract, safe_child

logger = logging.getLogger(__name__)


def _librarian():
    """The composed Librarian class (late import: it is built from these mixins)."""
    from ..librarian import Librarian

    return Librarian


class SkillsMixin(LibrarianBase):
    """SKILL.md parsing/reconciliation and skill imports (agent-level and project-level)."""

    @staticmethod
    def _parse_skill_md_version(skill_md_path: Path) -> str:
        """Extract version from SKILL.md frontmatter.

        Checks top-level 'version' and 'metadata.version' (open-standard location).
        Both resolve identically via the flat parser — indented keys are flattened.
        """
        fm = _librarian()._parse_skill_md_frontmatter(skill_md_path)
        return fm.get("version", "")

    @staticmethod
    def _parse_skill_md_frontmatter(skill_md_path: Path) -> dict:
        """Parse all key: value pairs from SKILL.md YAML frontmatter block.

        Returns an empty dict when the file has no --- block or on any error.
        Values that contain a comma-separated list are returned as strings;
        callers split them as needed.
        """
        try:
            content = skill_md_path.read_text(encoding="utf-8").lstrip()
            if not content.startswith("---"):
                return {}
            end = content.index("---", 3)
            block = content[3:end]
            result: dict = {}
            for line in block.splitlines():
                if ":" not in line:
                    continue
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()
                if key:
                    result[key] = value
            return result
        except (OSError, ValueError) as exc:
            logger.warning("cannot read frontmatter of %s: %s", skill_md_path, exc)
            return {}

    @staticmethod
    def _validate_and_reconcile_skill_manifest(skill_dir: Path) -> None:
        """Parse SKILL.md frontmatter, validate required fields, and keep
        skill-manifest.json in sync.  Raises ValueError on validation failure.

        Open-standard requirements (agentskills.io — name + description only):
        - Required frontmatter fields: name, description
        - version, triggers are optional (open-standard compatible)
        - name must match the directory name
        - If skill-manifest.json is absent: generate it from frontmatter
        - If skill-manifest.json is present: assert name consistency
        """
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return  # no SKILL.md — nothing to parse

        fm = _librarian()._parse_skill_md_frontmatter(skill_md)
        if not fm:
            return  # no frontmatter — nothing to validate

        # Open standard requires only name + description
        required = ("name", "description")
        missing = [f for f in required if not fm.get(f)]
        if missing:
            raise ValueError(f"SKILL.md frontmatter missing required fields: {', '.join(missing)}")

        fm_name = fm["name"]
        # version and triggers are optional per open standard
        fm_version = fm.get("version", "")
        fm_triggers = fm.get("triggers", "")

        manifest_path = skill_dir / "skill-manifest.json"
        if not manifest_path.exists():
            # Auto-generate from frontmatter; only include optional fields if present
            data: dict = {
                "name": fm_name,
                "description": fm["description"],
            }
            if fm_version:
                data["version"] = fm_version
            if fm_triggers:
                data["triggers"] = fm_triggers
            _atomic_write_json(manifest_path, data)
        else:
            # Reconcile: update name/description; merge optional fields if present
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                logger.warning("replacing unreadable %s: %s", manifest_path, exc)
                data = {}
            if data.get("name") and data["name"] != fm_name:
                raise ValueError(f"skill-manifest.json name '{data['name']}' conflicts with SKILL.md name '{fm_name}'")
            data["name"] = fm_name
            data["description"] = fm["description"]
            if fm_version:
                data["version"] = fm_version
            if fm_triggers:
                data["triggers"] = fm_triggers
            _atomic_write_json(manifest_path, data)

    @classmethod
    def _install_skill(cls, skill_source: str, skills_dir: Path) -> str:
        """Normalize a skill (directory or ZIP) and install it as ``skills_dir/<name>``; returns the name.

        Shared by agent-level and project-level imports: frontmatter is reconciled first (#134), the
        skill-manifest.json may be nested (some ZIP exports), and the name must be a safe path component (#185).
        """
        source_path = Path(skill_source).resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Skill source not found: {skill_source}")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            if zipfile.is_zipfile(source_path):
                with zipfile.ZipFile(source_path, "r") as zf:
                    _safe_extract(zf, temp_path)
            elif source_path.is_dir():
                shutil.copytree(source_path, temp_path, dirs_exist_ok=True)
            else:
                raise ValueError("Skill source must be a directory or a ZIP file.")

            # Auto-generates skill-manifest.json from SKILL.md frontmatter when absent (#134).
            _librarian()._validate_and_reconcile_skill_manifest(temp_path)

            manifest_file = temp_path / "skill-manifest.json"
            if not manifest_file.exists():
                manifests = list(temp_path.rglob("skill-manifest.json"))
                if not manifests:
                    raise FileNotFoundError("skill-manifest.json not found in the source.")
                manifest_file = manifests[0]
                temp_path = manifest_file.parent

            try:
                skill_data = json.loads(manifest_file.read_text())
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON in {manifest_file}") from None
            if "name" not in skill_data:
                raise ValueError("skill-manifest.json must contain a 'name' field.")

            skill_name = skill_data["name"]
            target_dir = safe_child(skills_dir, skill_name, "skill")
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(temp_path, target_dir)
        return skill_name

    def import_skill(self, skill_source: str) -> str:
        """Import a standalone skill (directory or ZIP) into this agent's skills/ directory."""
        skill_name = self._install_skill(skill_source, self.agent_root / "skills")
        self.sync()
        return skill_name

    @classmethod
    def import_skill_to_project(cls, skill_source: str, project_root: str) -> str:
        """Import a skill into the project-level .ai/skills/ and rebuild every adapter brief."""
        skill_name = cls._install_skill(skill_source, Path(project_root).resolve() / HARNESS_ROOT / "skills")
        cls.update_harness_files(project_root)
        return skill_name
