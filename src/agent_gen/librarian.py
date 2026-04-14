"""Librarian — manifest integrity engine for the Agent Factory."""

import json
import os
import re
import zipfile
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

TRACKED_DIRS = ["skills", "commands", "docs", "scripts", "orchestration"]
MANIFEST_FILE = "agent-manifest.json"
HARNESS_ROOT = ".ai"
CONTEXT_FILE = "AgentFactory.md"  # single source of truth for all CLI instructions


def _safe_extract(zf: zipfile.ZipFile, target_dir: Path) -> None:
    """Extract ZIP members, rejecting any that would escape target_dir (zip-slip guard)."""
    target_resolved = target_dir.resolve()
    for member in zf.infolist():
        dest = (target_dir / member.filename).resolve()
        if dest != target_resolved and not str(dest).startswith(str(target_resolved) + os.sep):
            raise ValueError(
                f"Unsafe ZIP entry '{member.filename}' — zip slip attack blocked."
            )
        zf.extract(member, target_dir)


def _sanitize_for_markdown(text: object) -> str:
    """
    Strip prompt-injection vectors before embedding text in AI-readable markdown.

    Removes HTML comments (used as AI instruction markers), flattens newlines
    (prevents multi-line injection), and caps length at 200 chars.
    """
    if not isinstance(text, str):
        text = str(text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)  # strip HTML comments
    text = " ".join(text.splitlines())                        # flatten newlines
    text = re.sub(r"\s+", " ", text).strip()
    return text[:200]


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
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=path,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "untracked"


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
        "AGENTS.md": "orchestration/AGENTS.md"
    },
    "gemini": {
        ".gemini/skills": "skills",
        ".gemini/extensions": "skills/extensions",
        "GEMINI.md": "docs/GEMINI.md",
        "AGENTS.md": "orchestration/AGENTS.md"
    },
    "codex": {
        ".codex/prompts": "skills/prompts",
        "codex.md": "docs/codex.md",
        ".codex/templates": "docs/templates",
        ".codex/workflows": "orchestration/workflows",
        "AGENTS.md": "orchestration/AGENTS.md"
    }
}

# ---------------------------------------------------------------------------
# FormatSwitch — per-CLI compiled brief registry
# ---------------------------------------------------------------------------

_FORMAT_REGISTRY: dict[str, dict] = {
    "claude": {
        "output": "brief.md",
        "header": "# AgentFactory Intelligence Brief — Claude Code",
        "root_files": ["CLAUDE.md"],
        "folder_symlink": ".claude",
        "wiring": {
            "skills": "../../skills",
            "commands": "../../commands",
        },
        "config_file": "settings.json",
        "config_default": "{}",
        "skill_path_template": ".claude/skills/{name}/SKILL.md",
        "command_prefix": "/",
        "sections": {
            "skills": "_fmt_skills_table",
            "commands": "_fmt_commands_list",
            "agents": "_fmt_agents_list",
            "rules": "_fmt_rules_list",
        },
        "section_order": ["skills", "commands", "agents", "rules"],
    },
    "codex": {
        "output": "brief.md",
        "header": "# AgentFactory Intelligence Brief — Codex CLI",
        "root_files": ["AGENTS.md", "CODEX.md"],
        "folder_symlink": ".codex",
        "wiring": {
            "skills": "../../skills",
            "prompts": "../../commands",
        },
        "config_file": "config.toml",
        "config_default": 'model = "o4-mini"\n',
        "skill_path_template": ".codex/skills/{name}/SKILL.md",
        "command_prefix": "",
        "sections": {
            "skills": "_fmt_skills_blocks",
            "commands": None,
            "agents": "_fmt_agents_list",
            "rules": "_fmt_rules_list",
        },
        "section_order": ["skills", "agents", "rules"],
    },
    "gemini": {
        "output": "brief.md",
        "header": "# AgentFactory Intelligence Brief — Gemini CLI",
        "root_files": ["GEMINI.md"],
        "folder_symlink": ".gemini",
        "wiring": {
            "tools": "../../skills",
        },
        "config_file": "config.json",
        "config_default": "{}",
        "skill_path_template": ".gemini/tools/{name}/SKILL.md",
        "command_prefix": "",
        "sections": {
            "skills": "_fmt_skills_tools",
            "commands": None,
            "agents": "_fmt_agents_list",
            "rules": "_fmt_rules_list",
        },
        "section_order": ["skills", "agents", "rules"],
    },
}


def _fmt_skills_table(skills: list, config: dict) -> str:
    if not skills:
        return "## Available Skills\n\nNo skills imported yet."
    template = config["skill_path_template"]
    header = "## Available Skills\n\n| Skill | When to invoke | Path |\n|-------|----------------|------|"
    rows = []
    for s in skills:
        path = template.replace("{name}", s["name"])
        rows.append(f"| {s['name']} | {s.get('triggers', '')} | `{path}` |")
    return header + "\n" + "\n".join(rows)


def _fmt_skills_blocks(skills: list, config: dict) -> str:
    if not skills:
        return "## Available Skills\n\nNo skills imported yet."
    template = config["skill_path_template"]
    blocks = ["## Available Skills"]
    for s in skills:
        path = template.replace("{name}", s["name"])
        block = (
            f"### {s['name']}\n"
            f"- Description: {s.get('description', 'No description')}\n"
            f"- See: {path}\n"
            f"- Use when: {s.get('triggers', 'see skill documentation')}"
        )
        blocks.append(block)
    return "\n\n".join(blocks)


def _fmt_skills_tools(skills: list, config: dict) -> str:
    if not skills:
        return "## Available Tools\n\nNo tools imported yet."
    template = config["skill_path_template"]
    blocks = ["## Available Tools"]
    for s in skills:
        path = template.replace("{name}", s["name"])
        input_val = s.get('input_hint') or s.get('triggers') or 'see tool documentation'
        block = (
            f"### {s['name']}\n"
            f"- Description: {s.get('description', 'No description')}\n"
            f"- Input: {input_val}\n"
            f"- See: {path}"
        )
        blocks.append(block)
    return "\n\n".join(blocks)


def _fmt_commands_list(commands: list, config: dict) -> str:
    if not commands:
        return "## Commands\n\nNo commands registered."
    prefix = config.get("command_prefix", "")
    lines = ["## Commands"]
    for c in commands:
        lines.append(f"- `{prefix}{c['name']}` — {c.get('description', 'No description')}")
    return "\n".join(lines)


def _fmt_agents_list(agents: list, config: dict) -> str:
    if not agents:
        return "## Registered Agents\n\nNo agents registered."
    lines = ["## Registered Agents"]
    for a in agents:
        lines.append(f"- **{a['name']}**: {a.get('description', 'No description')}")
    return "\n".join(lines)


def _fmt_rules_list(rules: list, config: dict) -> str:
    if not rules:
        return "## Behavior Rules\n\nNo rules defined."
    lines = ["## Behavior Rules"]
    for r in rules:
        lines.append(f"- {r['summary']}")
    return "\n".join(lines)


_FORMATTER_DISPATCH: dict = {
    "_fmt_skills_table":  _fmt_skills_table,
    "_fmt_skills_blocks": _fmt_skills_blocks,
    "_fmt_skills_tools":  _fmt_skills_tools,
    "_fmt_commands_list": _fmt_commands_list,
    "_fmt_agents_list":   _fmt_agents_list,
    "_fmt_rules_list":    _fmt_rules_list,
}


class Librarian:
    def __init__(self, agent_root: str):
        self.agent_root = Path(agent_root).resolve()
        self.manifest_path = self.agent_root / MANIFEST_FILE

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
            matches = sum(1 for trigger in rules.keys() if (source_path / trigger).exists())
            if matches >= 1:
                all_matching_profiles.append(profile)

        if all_matching_profiles:
            detected_profile = all_matching_profiles[0]

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

        return detected_profile, mapping, all_matching_profiles

    def migrate(self, mapping: dict[str, str]) -> None:
        """
        Execute the migration based on a mapping with a safe rollback mechanism.
        """
        import tempfile
        import shutil

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

                # 3. If everything succeeds, swap the staging directory with the original
                shutil.rmtree(self.agent_root)
                shutil.move(str(staging_path), str(self.agent_root))

            except Exception as exc:
                # Rollback is automatic since we operated on the staging copy.
                # The original agent_root is left untouched.
                raise RuntimeError(f"Migration failed and was safely rolled back. Reason: {exc}")

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
        import ast

        # Regex for <!-- @depends-on: path/to/resource -->
        MD_DEP_REGEX = re.compile(r"<!--\s*@depends-on:\s*([^\s-]+)\s*-->")
        
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
                    if full_path.suffix == ".py":
                        try:
                            tree = ast.parse(content, filename=str(full_path))
                            for node in ast.walk(tree):
                                if isinstance(node, ast.Import):
                                    for alias in node.names:
                                        root_mod = alias.name.split(".")[0]
                                        if root_mod in script_map:
                                            deps.add(script_map[root_mod])
                                elif isinstance(node, ast.ImportFrom):
                                    if node.module:
                                        root_mod = node.module.split(".")[0]
                                        if root_mod in script_map:
                                            deps.add(script_map[root_mod])
                        except SyntaxError:
                            pass

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
        
        # Propagate changes to the global registry if installed
        Librarian.sync_to_global(manifest, ".")
        
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
            "untracked_files": [],
            "invalid_skill_manifests": [],
            "skill_version_drift": [],
            "repo_state_warnings": [],
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
                                report["invalid_skill_manifests"].append(str(manifest_file.relative_to(self.agent_root)))
                        except Exception:
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
                            except Exception:
                                pass

        # Gap 2 & 3: repo-state.md checks (only meaningful for project-level audit)
        repo_state = self.agent_root / "skills" / "git-versioning" / "references" / "repo-state.md"
        if repo_state.exists():
            report["repo_state_warnings"].extend(self._check_repo_state(repo_state))

        return report

    @staticmethod
    def _parse_skill_md_version(skill_md_path: Path) -> str:
        """Extract version from SKILL.md YAML frontmatter (--- block)."""
        try:
            content = skill_md_path.read_text()
            if not content.startswith("---"):
                return ""
            end = content.index("---", 3)
            frontmatter = content[3:end]
            for line in frontmatter.splitlines():
                if line.strip().startswith("version:"):
                    return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return ""

    @staticmethod
    def _check_repo_state(repo_state_path: Path) -> list[str]:
        """Gap 2 & 3: warn if latest git tag not in repo-state.md or remote URL mismatch."""
        warnings = []
        content = repo_state_path.read_text()

        # Gap 2: latest git tag not in repo-state.md
        try:
            latest_tag = subprocess.check_output(
                ["git", "describe", "--tags", "--abbrev=0"],
                stderr=subprocess.DEVNULL,
                cwd=str(repo_state_path.parent),
            ).decode().strip()
            if latest_tag and latest_tag not in content:
                warnings.append(f"repo-state.md missing latest git tag: {latest_tag}")
        except subprocess.CalledProcessError:
            pass  # no tags yet

        # Gap 3: remote URL mismatch
        try:
            actual_url = subprocess.check_output(
                ["git", "remote", "get-url", "origin"],
                stderr=subprocess.DEVNULL,
                cwd=str(repo_state_path.parent),
            ).decode().strip()
            if actual_url:
                # Normalize: strip protocol (https://, git@, etc.) and .git suffix
                normalized = actual_url.removesuffix(".git")
                for prefix in ("https://", "http://", "git@", "ssh://"):
                    normalized = normalized.removeprefix(prefix)
                normalized = normalized.replace(":", "/")  # git@host:org/repo → host/org/repo
                if normalized not in content and actual_url not in content:
                    warnings.append(
                        f"repo-state.md remote URL mismatch: git remote={actual_url}"
                    )
        except subprocess.CalledProcessError:
            pass

        return warnings

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

    def import_skill(self, skill_source: str) -> str:
        """
        Import a standalone skill into this agent's skills/ directory.
        Supports both directories and ZIP files.
        """
        source_path = Path(skill_source).resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Skill source not found: {skill_source}")

        import tempfile
        import shutil

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            if zipfile.is_zipfile(source_path):
                with zipfile.ZipFile(source_path, 'r') as zf:
                    _safe_extract(zf, temp_path)
            elif source_path.is_dir():
                # Copy content to temp area to normalize
                shutil.copytree(source_path, temp_path, dirs_exist_ok=True)
            else:
                raise ValueError("Skill source must be a directory or a ZIP file.")

            # Look for skill-manifest.json
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
                    raise ValueError(f"Invalid JSON in {manifest_file}")

            if "name" not in skill_data:
                raise ValueError("skill-manifest.json must contain a 'name' field.")

            skill_name = skill_data["name"]
            target_dir = self.agent_root / "skills" / skill_name

            # Ensure skills directory exists
            target_dir.parent.mkdir(parents=True, exist_ok=True)

            if target_dir.exists():
                shutil.rmtree(target_dir)

            # Copy normalized skill to agent
            shutil.copytree(temp_path, target_dir)

        self.sync()
        return skill_name

    @staticmethod
    def unpack(zip_path: str, target_root: str) -> dict:
        """
        Unpack a portable unit into target_root, honouring the manifest's
        directory layout.  Returns the imported manifest.
        """
        zip_path = Path(zip_path).resolve()
        target_root = Path(target_root).resolve()

        with zipfile.ZipFile(zip_path) as zf:
            _safe_extract(zf, target_root)

        manifest_path = target_root / MANIFEST_FILE
        if not manifest_path.exists():
            raise FileNotFoundError("Archive has no agent-manifest.json — invalid package.")

        with open(manifest_path) as f:
            return json.load(f)

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
        lock_path = cls._global_manifest_path(project_root).with_suffix('.json.lock')
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

                with open(global_path, "w") as f:
                    json.dump(global_manifest, f, indent=2)

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
                global_manifest["agents"][name]["description"] = agent_manifest.get("description", "No description provided.")
                global_manifest["agents"][name]["git_ref"] = agent_manifest.get("git_ref", "unknown")
                global_manifest["agents"][name]["resources"] = agent_manifest.get("resources", {})
                
                with open(global_path, "w") as f:
                    json.dump(global_manifest, f, indent=2)
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
    def update_harness_files(cls, project_root: str) -> None:
        """
        Update project-level harness files (CLAUDE.md, GEMINI.md, AGENTS.md)
        with the current list of registered agents.
        """
        global_path = cls._global_manifest_path(project_root)
        project_path = Path(project_root).resolve()
        
        with cls._get_lock(project_root):
            if not global_path.exists():
                return

            with open(global_path) as f:
                global_manifest = json.load(f)

            agents = global_manifest.get("agents", {})
            
            # Build the agent registry text
            agent_registry_lines = ["<!-- @agent-registry:start -->"]
            if not agents:
                agent_registry_lines.append("_No agents currently imported._")
            else:
                for name, data in sorted(agents.items()):
                    desc = _sanitize_for_markdown(data.get("description", "No description provided."))
                    safe_name = re.sub(r"[^\w\-]", "-", str(name)).strip("-")
                    agent_registry_lines.append(f"- **{safe_name}**: {desc} (See: `{HARNESS_ROOT}/agents/{safe_name}/docs/CLAUDE.md`)")
            agent_registry_lines.append("<!-- @agent-registry:end -->")
            agent_registry_text = "\n".join(agent_registry_lines)

            # Build the skills registry text for root project
            skills_dir = project_path / HARNESS_ROOT / "skills"
            skill_registry_lines = ["<!-- @skills-registry:start -->"]
            root_skills = []
            if skills_dir.exists() and skills_dir.is_dir():
                for manifest_file in skills_dir.rglob("skill-manifest.json"):
                    try:
                        with open(manifest_file) as f:
                            s_data = json.load(f)
                        s_name = s_data.get("name", "Unknown")
                        s_desc = _sanitize_for_markdown(s_data.get("description", "No description provided."))
                        rel_path = manifest_file.parent.relative_to(project_path)

                        # Assuming main skill file is SKILL.md
                        skill_md_path = manifest_file.parent / "SKILL.md"
                        doc_ref = f"`{rel_path}/SKILL.md`" if skill_md_path.exists() else f"`{rel_path}`"

                        root_skills.append((s_name, s_desc, doc_ref))
                    except Exception:
                        continue
            
            if not root_skills:
                skill_registry_lines.append("_No global skills currently imported._")
            else:
                for s_name, s_desc, doc_ref in sorted(root_skills, key=lambda x: x[0]):
                    safe_s_name = re.sub(r"[^\w\-]", "-", str(s_name)).strip("-")
                    skill_registry_lines.append(f"- **{safe_s_name}**: {s_desc} (See: {doc_ref})")
            skill_registry_lines.append("<!-- @skills-registry:end -->")
            skill_registry_text = "\n".join(skill_registry_lines)

            # Targeted files: single .ai/.CLAUDE.md is the source of truth for all CLIs;
            # README.md gets registry updates too for human readers.
            targets = [
                f"{HARNESS_ROOT}/{CONTEXT_FILE}",
                "README.md",
            ]

            agent_pattern = re.compile(r"<!-- @agent-registry:start -->.*?<!-- @agent-registry:end -->", re.DOTALL)
            skill_pattern = re.compile(r"<!-- @skills-registry:start -->.*?<!-- @skills-registry:end -->", re.DOTALL)

            updated_paths = set()
            for target_name in targets:
                target_path = project_path / target_name

                # Resolve symlinks to avoid writing the same underlying file twice
                resolved_path = target_path.resolve()
                if resolved_path in updated_paths:
                    continue

                # Create AgentFactory.md stub if missing (first run after init)
                if not target_path.exists() and not target_path.is_symlink():
                    if target_name.endswith(CONTEXT_FILE):
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        target_path.write_text(
                            f"# Project Context\n\n{agent_registry_text}\n",
                            encoding="utf-8",
                        )
                        updated_paths.add(resolved_path)
                    continue

                if not target_path.exists():
                    continue

                content = target_path.read_text(encoding="utf-8")

                # Update Agents
                if "<!-- @agent-registry:start -->" in content:
                    content = agent_pattern.sub(agent_registry_text, content)
                else:
                    content = content.strip() + f"\n\n## Registered Agents\n{agent_registry_text}\n"

                # Update Skills
                if "<!-- @skills-registry:start -->" in content:
                    content = skill_pattern.sub(skill_registry_text, content)

                target_path.write_text(content, encoding="utf-8")
                updated_paths.add(resolved_path)

        # Ensure adapter symlink wiring is complete after every harness update
        cls._ensure_adapter_wiring(project_root)
        cls._compile_adapter_briefs(project_root)
        cls._migrate_root_symlinks(project_root)

    # ------------------------------------------------------------------
    # Remote import helpers
    # ------------------------------------------------------------------

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
        lib = Librarian(agent_dir)
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
                    desc = (
                        context["agents"].get(stem, "")
                        or _extract_first_paragraph(dest_md)
                        or f"{stem} sub-agent"
                    )
                    sm_path.write_text(json.dumps({
                        "name": stem,
                        "version": "1.0.0",
                        "description": desc[:200],
                    }, indent=2))

    # ------------------------------------------------------------------
    # FormatSwitch — data collectors
    # ------------------------------------------------------------------

    @classmethod
    def _collect_skills_data(cls, project_root: str) -> list:
        skills_dir = Path(project_root) / HARNESS_ROOT / "skills"
        if not skills_dir.exists():
            return []
        skills = []
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            manifest = skill_dir / "skill-manifest.json"
            if manifest.exists():
                try:
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
                skills.append({
                    "name": skill_dir.name,
                    "description": data.get("description", ""),
                    "triggers": data.get("triggers", data.get("when_to_use", "")),
                    "input_hint": data.get("input", ""),
                })
            else:
                skills.append({"name": skill_dir.name, "description": "", "triggers": "", "input_hint": ""})
        return skills

    @classmethod
    def _collect_agents_data(cls, project_root: str) -> list:
        manifest_path = Path(project_root) / HARNESS_ROOT / "agent-manifest.json"
        if not manifest_path.exists():
            return []
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return [
            {"name": name, "description": info.get("description", "No description")}
            for name, info in data.get("agents", {}).items()
        ]

    @classmethod
    def _collect_commands_data(cls, project_root: str) -> list:
        commands_dir = Path(project_root) / HARNESS_ROOT / "commands"
        if not commands_dir.exists():
            return []
        commands = []
        for cmd_file in sorted(commands_dir.glob("*.md")):
            content = cmd_file.read_text(encoding="utf-8").strip()
            commands.append({
                "name": cmd_file.stem,
                "description": cls._extract_first_description(content),
            })
        return commands

    @classmethod
    def _collect_rules_data(cls, project_root: str) -> list:
        rules_dir = Path(project_root) / HARNESS_ROOT / "rules"
        if not rules_dir.exists():
            return []
        rules = []
        for rule_file in sorted(rules_dir.glob("*.md")):
            content = rule_file.read_text(encoding="utf-8").strip()
            summary = cls._extract_first_bullet_or_line(content)
            if summary:
                rules.append({"name": rule_file.stem, "summary": summary})
        return rules

    @staticmethod
    def _extract_first_bullet_or_line(content: str) -> str:
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("<!--"):
                continue
            if stripped.startswith("- ") or stripped.startswith("* "):
                return stripped[2:].strip()
            return stripped
        return ""

    @staticmethod
    def _extract_first_description(content: str) -> str:
        lines = content.splitlines()
        in_frontmatter = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if i == 0 and stripped == "---":
                in_frontmatter = True
                continue
            if in_frontmatter:
                if stripped == "---":
                    in_frontmatter = False
                    continue
                if stripped.startswith("description:"):
                    return stripped.split(":", 1)[1].strip().strip('"').strip("'")
                continue
            if stripped and not stripped.startswith("#"):
                return stripped
        return "No description"

    # ------------------------------------------------------------------
    # FormatSwitch — compilation driver
    # ------------------------------------------------------------------

    @classmethod
    def _render_brief(cls, adapter_name: str, config: dict, data: dict) -> str:
        sections = []
        header = (
            f"{config['header']}\n"
            f"<!-- @compiled-by: agentfactory-gen -->\n"
            f"<!-- @source: .ai/ -->\n"
            f"<!-- @adapter: {adapter_name} -->\n"
            f"<!-- @recompile: agentfactory-gen brief -->"
        )
        sections.append(header)
        for section_key in config["section_order"]:
            formatter_name = config["sections"].get(section_key)
            if formatter_name is None:
                continue
            formatter_fn = _FORMATTER_DISPATCH.get(formatter_name)
            if formatter_fn is None:
                continue
            rendered = formatter_fn(data.get(section_key, []), config)
            if rendered:
                sections.append(rendered)
        return "\n\n".join(sections) + "\n"

    @classmethod
    def _compile_adapter_briefs(cls, project_root: str) -> None:
        """Compile brief.md for every activated adapter using FormatSwitch."""
        import click as _click
        adapters_root = Path(project_root) / HARNESS_ROOT / "adapters"
        if not adapters_root.exists():
            return

        data = {
            "skills":   cls._collect_skills_data(project_root),
            "agents":   cls._collect_agents_data(project_root),
            "commands": cls._collect_commands_data(project_root),
            "rules":    cls._collect_rules_data(project_root),
        }

        for adapter_name, config in _FORMAT_REGISTRY.items():
            adapter_dir = adapters_root / adapter_name
            if not adapter_dir.exists():
                continue
            brief_path = adapter_dir / config["output"]
            try:
                new_content = cls._render_brief(adapter_name, config, data)
                if brief_path.exists() and brief_path.read_text(encoding="utf-8") == new_content:
                    continue
                brief_path.write_text(new_content, encoding="utf-8")
            except Exception as e:
                _click.echo(f"Warning: failed to compile brief for {adapter_name}: {e}", err=True)

    @classmethod
    def _migrate_root_symlinks(cls, project_root: str) -> None:
        """Update legacy root symlinks that point to AgentFactory.md → per-CLI brief.md."""
        root = Path(project_root)
        for adapter_name, config in _FORMAT_REGISTRY.items():
            adapter_dir = root / HARNESS_ROOT / "adapters" / adapter_name
            brief_path = adapter_dir / config["output"]
            if not adapter_dir.exists() or not brief_path.exists():
                continue
            brief_target = f"{HARNESS_ROOT}/adapters/{adapter_name}/{config['output']}"
            for root_file in config["root_files"]:
                root_path = root / root_file
                if root_path.is_symlink():
                    current = os.readlink(str(root_path))
                    if "AgentFactory.md" in current:
                        root_path.unlink()
                        root_path.symlink_to(brief_target)

    @classmethod
    def _ensure_adapter_wiring(cls, project_root: str) -> None:
        """
        Idempotently create missing adapter symlinks driven by _FORMAT_REGISTRY.

        Reads each adapter's wiring map from the registry — no hardcoded lists.
        This fixes #94 by automatically including the Codex skills symlink.
        """
        adapters_root = Path(project_root).resolve() / HARNESS_ROOT / "adapters"
        for adapter_name, config in _FORMAT_REGISTRY.items():
            adapter_dir = adapters_root / adapter_name
            if not adapter_dir.exists():
                continue
            for link_name, link_target in config["wiring"].items():
                link_path = adapter_dir / link_name
                if link_path.is_symlink():
                    if os.readlink(str(link_path)) == link_target:
                        continue
                    link_path.unlink()
                elif link_path.exists():
                    continue  # real file/dir present — don't clobber
                link_path.symlink_to(link_target)

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
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "agents": {},
                }

            # Sanitize name and description at input boundary (#S5)
            name = re.sub(r"[^\w\-]", "-", str(imported_manifest["name"])).strip("-")[:64]
            if not name:
                raise ValueError("Imported manifest 'name' field is empty or invalid.")
            global_manifest["agents"][name] = {
                "version": str(imported_manifest.get("version", "0.0.0")),
                "description": _sanitize_for_markdown(imported_manifest.get("description", "No description provided.")),
                "imported_at": datetime.now(timezone.utc).isoformat(),
                "git_ref": str(imported_manifest.get("git_ref", "unknown")),
                "resources": imported_manifest["resources"],
            }

            with open(global_path, "w") as f:
                json.dump(global_manifest, f, indent=2)

        # Update harness files (Context Awareness)
        cls.update_harness_files(project_root)
