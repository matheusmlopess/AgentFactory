"""Librarian — manifest integrity engine for the Agent Factory."""

import json
import os
import zipfile
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

TRACKED_DIRS = ["skills", "commands", "docs", "scripts", "orchestration"]
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


CONVERSION_PROFILES = {
    "claude": {
        "prompts": "skills",
        "tools": "scripts",
        "instructions.md": "docs/CLAUDE.md",
        "claude_instructions.md": "docs/CLAUDE.md"
    },
    "gemini": {
        "system_instructions.md": "docs/GEMINI.md",
        "api_configs": "scripts"
    },
    "codex": {
        "functions": "skills",
        "logic": "orchestration"
    }
}


class Librarian:
    def __init__(self, agent_root: str):
        self.agent_root = Path(agent_root).resolve()
        self.manifest_path = self.agent_root / MANIFEST_FILE

    @classmethod
    def propose_retrofit(cls, source_dir: str) -> tuple[str, dict[str, str]]:
        """
        Analyze a directory and propose a mapping to AgentFactory standard.
        Returns (profile_name, mapping).
        """
        source_path = Path(source_dir).resolve()
        detected_profile = "auto"
        mapping: dict[str, str] = {}

        # Heuristic profile detection
        for profile, rules in CONVERSION_PROFILES.items():
            matches = 0
            for trigger in rules.keys():
                if (source_path / trigger).exists():
                    matches += 1
            if matches >= 1:
                detected_profile = profile
                break

        # Build mapping based on detected profile or auto
        rules = CONVERSION_PROFILES.get(detected_profile, {})
        
        # Add profile-specific rules
        for src, dest in rules.items():
            if (source_path / src).exists():
                mapping[src] = dest

        # Add auto-rules for common patterns if not already mapped
        auto_rules = {
            "skills": "skills",
            "commands": "commands",
            "docs": "docs",
            "scripts": "scripts",
            "src": "scripts",
            "orchestration": "orchestration"
        }
        for src, dest in auto_rules.items():
            if src not in mapping and (source_path / src).exists():
                mapping[src] = dest

        return detected_profile, mapping

    def migrate(self, mapping: dict[str, str]) -> None:
        """
        Execute the migration based on a mapping.
        """
        # 1. Create standard directories
        for d in TRACKED_DIRS:
            (self.agent_root / d).mkdir(parents=True, exist_ok=True)
            (self.agent_root / d / ".gitkeep").touch()

        # 2. Move files according to mapping
        for src_rel, dest_rel in mapping.items():
            src_path = self.agent_root / src_rel
            if not src_path.exists():
                continue
                
            dest_path = self.agent_root / dest_rel
            
            if src_path.is_dir():
                # If destination is also a directory, merge contents
                for item in src_path.iterdir():
                    target = dest_path / item.name
                    if target.exists() and target.is_dir() and item.is_dir():
                        # Simple recursive merge if both are dirs
                        for subitem in item.iterdir():
                            shutil.move(str(subitem), str(target / subitem.name))
                        item.rmdir()
                    else:
                        shutil.move(str(item), str(target))
                try:
                    src_path.rmdir()
                except OSError:
                    pass # Directory not empty or already moved
            else:
                # If destination is a directory, move file into it
                if dest_rel in TRACKED_DIRS:
                    shutil.move(str(src_path), str(dest_path / src_path.name))
                else:
                    # Specific file-to-file mapping
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src_path), str(dest_path))

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
                        # Skip hidden files
                        if file.name.startswith("."):
                            continue
                        resources[category].append(
                            str(file.relative_to(self.agent_root))
                        )
        return resources

    def _analyze_dependencies(self, resources: dict[str, list[str]]) -> dict[str, list[str]]:
        """
        Scan text files (markdown, python, etc) for explicit dependency annotations
        like <!-- @depends-on: skills/search.md --> or code imports.
        """
        import re
        
        # Regex for <!-- @depends-on: path/to/resource -->
        MD_DEP_REGEX = re.compile(r"<!--\s*@depends-on:\s*([^\s-]+)\s*-->")
        # Regex for basic python imports: import x or from x import y
        PY_IMPORT_REGEX = re.compile(r"^\s*(?:import|from)\s+([a-zA-Z0-9_\.]+)", re.MULTILINE)
        
        dependencies: dict[str, list[str]] = {}
        
        # Mapping of script stems to their relative paths for import detection
        script_map = {Path(p).stem: p for p in resources.get("scripts", [])}
        
        for category, paths in resources.items():
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
                    if full_path.suffix in [".py", ".md"]:
                        for match in PY_IMPORT_REGEX.finditer(content):
                            root_mod = match.group(1).split(".")[0]
                            if root_mod in script_map:
                                deps.add(script_map[root_mod])

                except Exception:
                    continue
                
                if deps:
                    dependencies[rel_path] = sorted(list(deps))
                    
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
            except Exception:
                continue
                
        return skills_metadata

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def init(self, name: str) -> dict:
        """Bootstrap a blank manifest for a newly deployed agent."""
        manifest = {
            "name": name,
            "version": "1.0.0",
            "description": f"AgentFactory-powered agent: {name}",
            "orchestration_plan": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
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
        manifest["synced_at"] = datetime.now(timezone.utc).isoformat()
        
        # Auto-detect orchestration plan
        if not manifest.get("orchestration_plan") and manifest["resources"].get("orchestration"):
            manifest["orchestration_plan"] = manifest["resources"]["orchestration"][0]

        # Intelligence layer
        manifest["dependencies"].update(self._analyze_dependencies(manifest["resources"]))
        manifest["skills_metadata"].update(self._parse_skill_manifests())

        self._save_manifest(manifest)
        return manifest

    def audit(self) -> dict:
        """
        Comprehensive check for integrity drift, missing metadata, and broken dependencies.
        """
        manifest = self._load_manifest()
        report = {
            "broken_resources": [],
            "broken_dependencies": [],
            "missing_skill_manifests": [],
            "untracked_files": []
        }
        
        # 1. Check resources
        present, missing = self.validate()
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
                    
        # 4. Check for skills without manifests (directories only)
        skills_dir = self.agent_root / "skills"
        if skills_dir.exists():
            for item in skills_dir.iterdir():
                if item.is_dir():
                    if not (item / "skill-manifest.json").exists():
                        # Skip if it's an empty dir (just has .gitkeep)
                        contents = [f for f in item.iterdir() if f.name != ".gitkeep"]
                        if contents:
                            report["missing_skill_manifests"].append(str(item.relative_to(self.agent_root)))
                        
        return report

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
    def deregister_from_project(cls, agent_name: str, project_root: str) -> None:
        """
        Remove an agent's entry from the project-level global manifest.
        """
        global_path = cls._global_manifest_path(project_root)

        if not global_path.exists():
            return

        with open(global_path) as f:
            global_manifest = json.load(f)

        if agent_name in global_manifest.get("agents", {}):
            del global_manifest["agents"][agent_name]

            with open(global_path, "w") as f:
                json.dump(global_manifest, f, indent=2)

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
    def update_harness_files(cls, project_root: str) -> None:
        """
        Update project-level harness files (CLAUDE.md, GEMINI.md, AGENTS.md)
        with the current list of registered agents.
        """
        global_path = cls._global_manifest_path(project_root)
        if not global_path.exists():
            return

        with open(global_path) as f:
            global_manifest = json.load(f)

        agents = global_manifest.get("agents", {})
        
        # Build the registry text
        registry_lines = ["<!-- @agent-registry:start -->"]
        if not agents:
            registry_lines.append("_No agents currently imported._")
        else:
            for name, data in sorted(agents.items()):
                desc = data.get("description", "No description provided.")
                # Truncate long descriptions
                if len(desc) > 100:
                    desc = desc[:97] + "..."
                registry_lines.append(f"- **{name}**: {desc} (See: `agents/{name}/docs/CLAUDE.md`)")
        registry_lines.append("<!-- @agent-registry:end -->")
        registry_text = "\n".join(registry_lines)

        targets = ["CLAUDE.md", "GEMINI.md", "AGENTS.md", "README.md"]
        import re
        pattern = re.compile(r"<!-- @agent-registry:start -->.*?<!-- @agent-registry:end -->", re.DOTALL)

        for target_name in targets:
            target_path = Path(project_root) / target_name
            
            # Special case for AGENTS.md - create if missing
            if not target_path.exists():
                if target_name == "AGENTS.md":
                    target_path.write_text(f"# Project Agents\n\n{registry_text}\n", encoding="utf-8")
                continue

            content = target_path.read_text(encoding="utf-8")
            if "<!-- @agent-registry:start -->" in content:
                new_content = pattern.sub(registry_text, content)
            else:
                # Append to the end if markers aren't present
                new_content = content.strip() + f"\n\n## Registered Agents\n{registry_text}\n"
            
            target_path.write_text(new_content, encoding="utf-8")

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
            "description": imported_manifest.get("description", "No description provided."),
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "git_ref": imported_manifest.get("git_ref", "unknown"),
            "resources": imported_manifest["resources"],
        }

        with open(global_path, "w") as f:
            json.dump(global_manifest, f, indent=2)

        # Update harness files (Context Awareness)
        cls.update_harness_files(project_root)
