"""Agent manifest lifecycle: load/save, crawl, dependencies, sync, audit, validate, wrap, unpack.

Split out of librarian.py (#189); `agent_gen.librarian` re-exports the public names."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .base import LibrarianBase
from .constants import MANIFEST_FILE, TRACKED_DIRS
from .safety import _atomic_write_json, _safe_extract
from .text import _git_ref

logger = logging.getLogger(__name__)


def _librarian():
    """The composed Librarian class (late import: it is built from these mixins)."""
    from ..librarian import Librarian

    return Librarian


class ManifestMixin(LibrarianBase):
    """Agent manifest lifecycle: load/save, crawl, dependencies, sync, audit, validate, wrap, unpack."""

    def __init__(self, agent_root: str):
        self.agent_root = Path(agent_root).resolve()
        self.manifest_path = self.agent_root / MANIFEST_FILE

    def _load_manifest(self) -> dict:
        if not self.manifest_path.exists():
            raise FileNotFoundError(
                f"No manifest found at {self.manifest_path}. Run `agentfactory-gen deploy <name>` first."
            )
        with open(self.manifest_path) as f:
            return json.load(f)

    def _save_manifest(self, manifest: dict) -> None:
        _atomic_write_json(self.manifest_path, manifest)

    def _crawl_resources(self) -> dict[str, list[str]]:
        resources: dict[str, list[str]] = {d: [] for d in TRACKED_DIRS}
        for category in TRACKED_DIRS:
            dir_path = self.agent_root / category
            if dir_path.exists():
                for file in sorted(dir_path.rglob("*")):
                    if file.is_file():
                        # Skip hidden files
                        if file.name.startswith("."):
                            continue
                        resources[category].append(str(file.relative_to(self.agent_root)))
        return resources

    def _analyze_dependencies(self, resources: dict[str, list[str]]) -> dict[str, list[str]]:
        """
        Scan text files (markdown, python, etc) for explicit dependency annotations
        like <!-- @depends-on: skills/search.md --> or code imports.
        """
        import ast

        # Regex for <!-- @depends-on: path/to/resource -->
        MD_DEP_REGEX = re.compile(r"<!--\s*@depends-on:\s*([^\s-]+)\s*-->")

        dependencies: dict[str, list[str]] = {}

        # Mapping of script stems to their relative paths for import detection
        script_map = {Path(p).stem: p for p in resources.get("scripts", [])}

        for paths in resources.values():
            for rel_path in paths:
                full_path = self.agent_root / rel_path
                if not full_path.exists() or not full_path.is_file():
                    continue

                # Only scan text files
                if full_path.suffix not in [".md", ".py", ".js", ".json", ".txt"]:
                    continue

                deps = set()
                try:
                    content = full_path.read_text(encoding="utf-8")

                    # 1. Look for explicit annotations
                    for match in MD_DEP_REGEX.finditer(content):
                        deps.add(match.group(1).strip())

                    # 2. Look for Python-style imports
                    if full_path.suffix == ".py":
                        try:
                            tree = ast.parse(content, filename=str(full_path))
                            for node in ast.walk(tree):
                                if isinstance(node, ast.Import):
                                    for alias in node.names:
                                        root_mod = alias.name.split(".")[0]
                                        if root_mod in script_map:
                                            deps.add(script_map[root_mod])
                                elif isinstance(node, ast.ImportFrom) and node.module:
                                    root_mod = node.module.split(".")[0]
                                    if root_mod in script_map:
                                        deps.add(script_map[root_mod])
                        except SyntaxError:
                            pass

                except (OSError, ValueError) as exc:
                    logger.warning("dependency scan skipped %s: %s", rel_path, exc)
                    continue

                if deps:
                    dependencies[rel_path] = sorted(deps)

        return dependencies

    def _parse_skill_manifests(self) -> dict[str, dict]:
        """
        Look for skill-manifest.json in skills/ subdirectories and extract metadata.
        """
        skills_metadata = {}
        skills_dir = self.agent_root / "skills"

        if not skills_dir.exists():
            return {}

        for manifest_file in skills_dir.rglob("skill-manifest.json"):
            try:
                with open(manifest_file) as f:
                    data = json.load(f)
                    rel_path = str(manifest_file.parent.relative_to(self.agent_root))
                    skills_metadata[rel_path] = data
            except (OSError, ValueError) as exc:
                logger.warning("skipping unreadable %s: %s", manifest_file, exc)
                continue

        return skills_metadata

    def init(self, name: str) -> dict:
        """Bootstrap a blank manifest for a newly deployed agent."""
        manifest: dict[str, Any] = {
            "name": name,
            "version": "1.0.0",
            "description": f"AgentFactory-powered agent: {name}",
            "orchestration_plan": None,
            "created_at": datetime.now(UTC).isoformat(),
            "git_ref": _git_ref(str(self.agent_root)),
            "resources": {d: [] for d in TRACKED_DIRS},
            "dependencies": {},
            "skills_metadata": {},
        }
        self._save_manifest(manifest)
        return manifest

    def sync(self) -> dict:
        """
        Crawl tracked directories and update the manifest to match
        what is actually on disk. Preserves manually set metadata.
        """
        manifest = self._load_manifest()

        # Preserve manually set fields if they exist
        manifest.setdefault("description", f"AgentFactory-powered agent: {manifest.get('name')}")
        manifest.setdefault("orchestration_plan", None)
        manifest.setdefault("dependencies", {})
        manifest.setdefault("skills_metadata", {})

        manifest["resources"] = self._crawl_resources()
        manifest["git_ref"] = _git_ref(str(self.agent_root))
        manifest["synced_at"] = datetime.now(UTC).isoformat()

        # Auto-detect orchestration plan
        if not manifest.get("orchestration_plan") and manifest["resources"].get("orchestration"):
            manifest["orchestration_plan"] = manifest["resources"]["orchestration"][0]

        # Intelligence layer
        manifest["dependencies"].update(self._analyze_dependencies(manifest["resources"]))
        manifest["skills_metadata"].update(self._parse_skill_manifests())

        self._save_manifest(manifest)

        # Propagate changes to the global registry if installed
        _librarian().sync_to_global(manifest, ".")

        return manifest

    def audit(self) -> dict:
        """
        Comprehensive check for integrity drift, missing metadata, and broken dependencies.
        """
        manifest = self._load_manifest()
        report: dict[str, Any] = {
            "broken_resources": [],
            "broken_dependencies": [],
            "missing_skill_manifests": [],
            "untracked_files": [],
            "invalid_skill_manifests": [],
            "skill_version_drift": [],
            "repo_state_warnings": [],
        }

        # 1. Check resources
        _present, missing = self.validate()
        report["broken_resources"] = missing

        # 2. Check dependencies
        for resource, deps in manifest.get("dependencies", {}).items():
            for dep in deps:
                if not (self.agent_root / dep).exists():
                    report["broken_dependencies"].append(f"{resource} -> {dep}")

        # 3. Check for untracked files in standard dirs
        disk_resources = self._crawl_resources()
        manifest_resources = manifest.get("resources", {})
        for cat, paths in disk_resources.items():
            m_paths = set(manifest_resources.get(cat, []))
            for p in paths:
                if p not in m_paths:
                    report["untracked_files"].append(p)

        # 4. Check for skills without manifests (directories only) and validate existing ones
        skills_dir = self.agent_root / "skills"
        if skills_dir.exists():
            for item in skills_dir.iterdir():
                if item.is_dir():
                    manifest_file = item / "skill-manifest.json"
                    if not manifest_file.exists():
                        # Skip if it's an empty dir (just has .gitkeep)
                        contents = [f for f in item.iterdir() if f.name != ".gitkeep"]
                        if contents:
                            report["missing_skill_manifests"].append(str(item.relative_to(self.agent_root)))
                    else:
                        # Validate the manifest
                        try:
                            with open(manifest_file) as f:
                                data = json.load(f)
                            if not isinstance(data, dict) or "name" not in data or "description" not in data:
                                report["invalid_skill_manifests"].append(
                                    str(manifest_file.relative_to(self.agent_root))
                                )
                        except (OSError, ValueError):
                            report["invalid_skill_manifests"].append(str(manifest_file.relative_to(self.agent_root)))

                        # Gap 1: Detect version drift between skill-manifest.json and SKILL.md frontmatter
                        skill_md = item / "SKILL.md"
                        if skill_md.exists() and manifest_file.exists():
                            try:
                                with open(manifest_file) as f:
                                    sm_data = json.load(f)
                                sm_version = sm_data.get("version", "")
                                skill_version = self._parse_skill_md_version(skill_md)
                                if sm_version and not skill_version:
                                    # SKILL.md exists but has no version frontmatter (#45)
                                    report["skill_version_drift"].append(
                                        f"{item.name}: SKILL.md missing version frontmatter (skill-manifest.json={sm_version})"
                                    )
                                elif skill_version and sm_version and skill_version != sm_version:
                                    report["skill_version_drift"].append(
                                        f"{item.name}: skill-manifest.json={sm_version} vs SKILL.md={skill_version}"
                                    )
                            except (OSError, ValueError) as exc:
                                logger.warning("version check skipped for %s: %s", item.name, exc)

        # Gap 2 & 3: repo-state.md checks (only meaningful for project-level audit)
        repo_state = self.agent_root / "skills" / "git-versioning" / "references" / "repo-state.md"
        if repo_state.exists():
            report["repo_state_warnings"].extend(self._check_repo_state(repo_state))

        return report

    @staticmethod
    def _check_repo_state(repo_state_path: Path) -> list[str]:
        """Gap 2 & 3: warn if latest git tag not in repo-state.md or remote URL mismatch."""
        warnings = []
        content = repo_state_path.read_text()

        # Gap 2: latest git tag not in repo-state.md
        try:
            latest_tag = (
                subprocess.check_output(
                    ["git", "describe", "--tags", "--abbrev=0"],
                    stderr=subprocess.DEVNULL,
                    cwd=str(repo_state_path.parent),
                )
                .decode()
                .strip()
            )
            if latest_tag and latest_tag not in content:
                warnings.append(f"repo-state.md missing latest git tag: {latest_tag}")
        except subprocess.CalledProcessError:
            pass  # no tags yet

        # Gap 3: remote URL mismatch
        try:
            actual_url = (
                subprocess.check_output(
                    ["git", "remote", "get-url", "origin"],
                    stderr=subprocess.DEVNULL,
                    cwd=str(repo_state_path.parent),
                )
                .decode()
                .strip()
            )
            if actual_url:
                # Normalize: strip protocol (https://, git@, etc.) and .git suffix
                normalized = actual_url.removesuffix(".git")
                for prefix in ("https://", "http://", "git@", "ssh://"):
                    normalized = normalized.removeprefix(prefix)
                normalized = normalized.replace(":", "/")  # git@host:org/repo → host/org/repo
                if normalized not in content and actual_url not in content:
                    warnings.append(f"repo-state.md remote URL mismatch: git remote={actual_url}")
        except subprocess.CalledProcessError:
            pass

        return warnings

    def validate(self) -> tuple[list[str], list[str]]:
        """
        Check every path in the manifest actually exists on disk.
        Returns (present, missing) path lists.
        """
        manifest = self._load_manifest()
        present: list[str] = []
        missing: list[str] = []
        for paths in manifest["resources"].values():
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
        _present, missing = self.validate()

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
            for paths in manifest["resources"].values():
                for rel_path in paths:
                    full = self.agent_root / rel_path
                    zf.write(full, rel_path)

        return archive_path

    @staticmethod
    def unpack(zip_path: str | Path, target_root: str | Path) -> dict:
        """
        Unpack a portable unit into target_root, honouring the manifest's
        directory layout.  Returns the imported manifest.
        """
        archive = Path(zip_path).resolve()
        root = Path(target_root).resolve()

        with zipfile.ZipFile(archive) as zf:
            _safe_extract(zf, root)

        manifest_path = root / MANIFEST_FILE
        if not manifest_path.exists():
            raise FileNotFoundError("Archive has no agent-manifest.json — invalid package.")

        with open(manifest_path) as f:
            return json.load(f)
