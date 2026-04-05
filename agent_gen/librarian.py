"""Librarian — manifest integrity engine for the Agent Factory."""

import json
import os
import zipfile
import subprocess
from datetime import datetime, timezone
from pathlib import Path

TRACKED_DIRS = ["skills", "commands", "docs"]
MANIFEST_FILE = "agent-manifest.json"


def _git_ref(path: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=path,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "untracked"


class Librarian:
    def __init__(self, agent_root: str):
        self.agent_root = Path(agent_root).resolve()
        self.manifest_path = self.agent_root / MANIFEST_FILE

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_manifest(self) -> dict:
        if not self.manifest_path.exists():
            raise FileNotFoundError(
                f"No manifest found at {self.manifest_path}. "
                "Run `agent-gen deploy <name>` first."
            )
        with open(self.manifest_path) as f:
            return json.load(f)

    def _save_manifest(self, manifest: dict) -> None:
        with open(self.manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

    def _crawl_resources(self) -> dict[str, list[str]]:
        resources: dict[str, list[str]] = {d: [] for d in TRACKED_DIRS}
        for category in TRACKED_DIRS:
            dir_path = self.agent_root / category
            if dir_path.exists():
                for file in sorted(dir_path.rglob("*")):
                    if file.is_file():
                        resources[category].append(
                            str(file.relative_to(self.agent_root))
                        )
        return resources

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def init(self, name: str) -> dict:
        """Bootstrap a blank manifest for a newly deployed agent."""
        manifest = {
            "name": name,
            "version": "1.0.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "git_ref": _git_ref(str(self.agent_root)),
            "resources": {d: [] for d in TRACKED_DIRS},
        }
        self._save_manifest(manifest)
        return manifest

    def sync(self) -> dict:
        """
        Crawl skills/, commands/, docs/ and update the manifest to match
        what is actually on disk.  Returns the updated manifest.
        """
        manifest = self._load_manifest()
        manifest["resources"] = self._crawl_resources()
        manifest["git_ref"] = _git_ref(str(self.agent_root))
        manifest["synced_at"] = datetime.now(timezone.utc).isoformat()
        self._save_manifest(manifest)
        return manifest

    def validate(self) -> tuple[list[str], list[str]]:
        """
        Check every path in the manifest actually exists on disk.
        Returns (present, missing) path lists.
        """
        manifest = self._load_manifest()
        present, missing = [], []
        for category, paths in manifest["resources"].items():
            for rel_path in paths:
                full = self.agent_root / rel_path
                (present if full.exists() else missing).append(rel_path)
        return present, missing

    def wrap(self, output_dir: str = ".") -> Path:
        """
        Validate → compress everything in the manifest into a zip.
        Returns the path to the created archive.
        """
        manifest = self._load_manifest()
        present, missing = self.validate()

        if missing:
            raise FileNotFoundError(
                f"Manifest validation failed — {len(missing)} file(s) missing:\n"
                + "\n".join(f"  ✗ {p}" for p in missing)
            )

        name = manifest["name"]
        version = manifest["version"]
        archive_name = f"{name}-v{version}.zip"
        archive_path = Path(output_dir).resolve() / archive_name

        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(self.manifest_path, MANIFEST_FILE)
            for category, paths in manifest["resources"].items():
                for rel_path in paths:
                    full = self.agent_root / rel_path
                    zf.write(full, rel_path)

        return archive_path

    @staticmethod
    def unpack(zip_path: str, target_root: str) -> dict:
        """
        Unpack a portable unit into target_root, honouring the manifest's
        directory layout.  Returns the imported manifest.
        """
        zip_path = Path(zip_path).resolve()
        target_root = Path(target_root).resolve()

        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(target_root)

        manifest_path = target_root / MANIFEST_FILE
        if not manifest_path.exists():
            raise FileNotFoundError("Archive has no agent-manifest.json — invalid package.")

        with open(manifest_path) as f:
            return json.load(f)

    @staticmethod
    def _global_manifest_path(project_root: str) -> Path:
        return Path(project_root).resolve() / "agent-manifest.json"

    @classmethod
    def register_in_project(cls, imported_manifest: dict, project_root: str) -> None:
        """
        The Handshake: merge an imported agent's manifest entry into the
        project-level global manifest.
        """
        global_path = cls._global_manifest_path(project_root)

        if global_path.exists():
            with open(global_path) as f:
                global_manifest = json.load(f)
        else:
            global_manifest = {
                "factory": "AgentFactory",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "agents": {},
            }

        name = imported_manifest["name"]
        global_manifest["agents"][name] = {
            "version": imported_manifest["version"],
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "git_ref": imported_manifest.get("git_ref", "unknown"),
            "resources": imported_manifest["resources"],
        }

        with open(global_path, "w") as f:
            json.dump(global_manifest, f, indent=2)
