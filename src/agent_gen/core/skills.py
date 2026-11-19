"""SKILL.md parsing/reconciliation and skill imports (agent-level and project-level).

Split out of librarian.py (#189); `agent_gen.librarian` re-exports the public names."""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from .constants import HARNESS_ROOT
from .safety import _atomic_write_json, _safe_extract, safe_child


def _librarian():
    """The composed Librarian class (late import: it is built from these mixins)."""
    from ..librarian import Librarian

    return Librarian


class SkillsMixin:
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
        except Exception:
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
            except Exception:
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

    def import_skill(self, skill_source: str) -> str:
        """
        Import a standalone skill into this agent's skills/ directory.
        Supports both directories and ZIP files.
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
                # Copy content to temp area to normalize
                shutil.copytree(source_path, temp_path, dirs_exist_ok=True)
            else:
                raise ValueError("Skill source must be a directory or a ZIP file.")

            # Validate and reconcile SKILL.md frontmatter first (#134).
            # This auto-generates skill-manifest.json from frontmatter when absent.
            _librarian()._validate_and_reconcile_skill_manifest(temp_path)

            # Look for skill-manifest.json (may have just been auto-generated)
            manifest_file = temp_path / "skill-manifest.json"
            if not manifest_file.exists():
                # Maybe it's nested (common in some zip exports)
                manifests = list(temp_path.rglob("skill-manifest.json"))
                if not manifests:
                    raise FileNotFoundError("skill-manifest.json not found in the source.")
                # Use the first one found and adjust temp_path
                manifest_file = manifests[0]
                temp_path = manifest_file.parent

            with open(manifest_file) as f:
                try:
                    skill_data = json.load(f)
                except json.JSONDecodeError:
                    raise ValueError(f"Invalid JSON in {manifest_file}") from None

            if "name" not in skill_data:
                raise ValueError("skill-manifest.json must contain a 'name' field.")

            skill_name = skill_data["name"]
            target_dir = safe_child(self.agent_root / "skills", skill_name, "skill")

            # Ensure skills directory exists
            target_dir.parent.mkdir(parents=True, exist_ok=True)

            if target_dir.exists():
                shutil.rmtree(target_dir)

            # Copy normalized skill to agent
            shutil.copytree(temp_path, target_dir)

        self.sync()
        return skill_name

    @classmethod
    def import_skill_to_project(cls, skill_source: str, project_root: str) -> str:
        """Import a skill directly into the project-level .ai/skills/ directory.

        This is the root-project variant of import_skill() — it targets
        HARNESS_ROOT/skills/<name> rather than an agent's skills/ subdirectory,
        and calls update_harness_files() to rebuild all adapter briefs.

        Returns the skill name.
        """
        source_path = Path(skill_source).resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Skill source not found: {skill_source}")

        target_root = Path(project_root).resolve() / HARNESS_ROOT

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            if zipfile.is_zipfile(source_path):
                with zipfile.ZipFile(source_path, "r") as zf:
                    _safe_extract(zf, temp_path)
            elif source_path.is_dir():
                shutil.copytree(source_path, temp_path, dirs_exist_ok=True)
            else:
                raise ValueError("Skill source must be a directory or a ZIP file.")

            # Validate and reconcile SKILL.md frontmatter first (#134).
            cls._validate_and_reconcile_skill_manifest(temp_path)

            manifest_file = temp_path / "skill-manifest.json"
            if not manifest_file.exists():
                manifests = list(temp_path.rglob("skill-manifest.json"))
                if not manifests:
                    raise FileNotFoundError("skill-manifest.json not found in the source.")
                manifest_file = manifests[0]
                temp_path = manifest_file.parent

            with open(manifest_file) as f:
                try:
                    skill_data = json.load(f)
                except json.JSONDecodeError:
                    raise ValueError(f"Invalid JSON in {manifest_file}") from None

            if "name" not in skill_data:
                raise ValueError("skill-manifest.json must contain a 'name' field.")

            skill_name = skill_data["name"]
            target_dir = safe_child(target_root / "skills", skill_name, "skill")
            target_dir.parent.mkdir(parents=True, exist_ok=True)

            if target_dir.exists():
                shutil.rmtree(target_dir)

            shutil.copytree(temp_path, target_dir)

        cls.update_harness_files(project_root)
        return skill_name
