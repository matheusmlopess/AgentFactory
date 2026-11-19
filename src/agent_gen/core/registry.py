"""The project-level registry (.ai/agent-manifest.json): register, sync, deregister, uninstall.

Split out of librarian.py (#189); `agent_gen.librarian` re-exports the public names."""

from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .base import LibrarianBase
from .constants import HARNESS_ROOT, MANIFEST_FILE
from .safety import _atomic_write_json, _sanitize_for_markdown


class ProjectRegistryMixin(LibrarianBase):
    """The project-level registry (.ai/agent-manifest.json): register, sync, deregister, uninstall."""

    @staticmethod
    def _global_manifest_path(project_root: str) -> Path:
        new = Path(project_root).resolve() / HARNESS_ROOT / MANIFEST_FILE
        legacy = Path(project_root).resolve() / MANIFEST_FILE
        # Fallback: project not yet migrated to .ai/ layout
        if not new.parent.exists() and legacy.exists():
            return legacy
        return new

    @classmethod
    def _get_lock(cls, project_root: str):
        from filelock import FileLock

        lock_path = cls._global_manifest_path(project_root).with_suffix(".json.lock")
        return FileLock(str(lock_path), timeout=10)

    @classmethod
    def deregister_from_project(cls, agent_name: str, project_root: str) -> None:
        """
        Remove an agent's entry from the project-level global manifest.
        """
        global_path = cls._global_manifest_path(project_root)

        with cls._get_lock(project_root):
            if not global_path.exists():
                return

            with open(global_path) as f:
                global_manifest = json.load(f)

            if agent_name in global_manifest.get("agents", {}):
                del global_manifest["agents"][agent_name]
                _atomic_write_json(global_path, global_manifest)

    @classmethod
    def sync_to_global(cls, agent_manifest: dict, project_root: str = ".") -> None:
        """
        Updates the agent's entry in the global registry if it is currently registered.
        Also runs update_harness_files to keep context files in sync.
        """
        global_path = cls._global_manifest_path(project_root)
        name = agent_manifest.get("name")
        if not name:
            return

        updated = False
        with cls._get_lock(project_root):
            if not global_path.exists():
                return

            with open(global_path) as f:
                global_manifest = json.load(f)

            if name in global_manifest.get("agents", {}):
                # Update fields that might have drifted locally
                global_manifest["agents"][name]["version"] = agent_manifest.get("version", "1.0.0")
                global_manifest["agents"][name]["description"] = agent_manifest.get(
                    "description", "No description provided."
                )
                global_manifest["agents"][name]["git_ref"] = agent_manifest.get("git_ref", "unknown")
                global_manifest["agents"][name]["resources"] = agent_manifest.get("resources", {})
                _atomic_write_json(global_path, global_manifest)
                updated = True

        if updated:
            cls.update_harness_files(project_root)

    def uninstall(self, project_root: str = ".") -> None:
        """
        Remove the agent directory and its registration from the project.
        """
        manifest = self._load_manifest()
        name = manifest["name"]

        # 1. Deregister from project manifest
        self.deregister_from_project(name, project_root)

        # 2. Remove directory
        if self.agent_root.exists():
            shutil.rmtree(self.agent_root)

    @classmethod
    def register_in_project(cls, imported_manifest: dict, project_root: str) -> None:
        """
        The Handshake: merge an imported agent's manifest entry into the
        project-level global manifest.
        """
        global_path = cls._global_manifest_path(project_root)

        with cls._get_lock(project_root):
            if global_path.exists():
                with open(global_path) as f:
                    global_manifest = json.load(f)
            else:
                global_manifest = {
                    "factory": "AgentFactory",
                    "created_at": datetime.now(UTC).isoformat(),
                    "agents": {},
                }

            # Sanitize name and description at input boundary (#S5)
            name = re.sub(r"[^\w\-]", "-", str(imported_manifest["name"])).strip("-")[:64]
            if not name:
                raise ValueError("Imported manifest 'name' field is empty or invalid.")
            global_manifest["agents"][name] = {
                "version": str(imported_manifest.get("version", "0.0.0")),
                "description": _sanitize_for_markdown(imported_manifest.get("description", "No description provided.")),
                "imported_at": datetime.now(UTC).isoformat(),
                "git_ref": str(imported_manifest.get("git_ref", "unknown")),
                "resources": imported_manifest["resources"],
            }

            _atomic_write_json(global_path, global_manifest)

        # Update harness files (Context Awareness)
        cls.update_harness_files(project_root)
