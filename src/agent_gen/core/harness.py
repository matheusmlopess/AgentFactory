"""Compiled adapter briefs, AgentFactory.md, root symlinks and adapter wiring.

Split out of librarian.py (#189); `agent_gen.librarian` re-exports the public names."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from .base import LibrarianBase
from .briefs import (
    _FORMAT_REGISTRY,
    _FORMATTER_DISPATCH,
    _collect_project_context,
    _fit_context_to_budget,
    _fmt_commands_list,
    _fmt_harness_identity,
    _fmt_rules_list,
)
from .constants import CONTEXT_FILE, HARNESS_ROOT
from .safety import _sanitize_for_markdown

logger = logging.getLogger(__name__)


class HarnessMixin(LibrarianBase):
    """Compiled adapter briefs, AgentFactory.md, root symlinks and adapter wiring."""

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
                    agent_registry_lines.append(
                        f"- **{safe_name}**: {desc} (See: `{HARNESS_ROOT}/agents/{safe_name}/docs/CLAUDE.md`)"
                    )
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
                    except (OSError, ValueError) as exc:
                        logger.warning("skipping unreadable skill manifest %s: %s", manifest_file, exc)
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
                else:
                    content = content.strip() + f"\n\n## Available Skills\n{skill_registry_text}\n"

                target_path.write_text(content, encoding="utf-8")
                updated_paths.add(resolved_path)

        # Ensure adapter symlink wiring is complete after every harness update
        cls._ensure_adapter_wiring(project_root)
        cls._compile_adapter_briefs(project_root)
        cls._migrate_root_symlinks(project_root)

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
                except (OSError, ValueError) as exc:
                    logger.warning("unreadable %s, listing the skill without metadata: %s", manifest, exc)
                    data = {}
                skills.append(
                    {
                        "name": skill_dir.name,
                        "description": data.get("description", ""),
                        "triggers": data.get("triggers", data.get("when_to_use", "")),
                        "input_hint": data.get("input", ""),
                    }
                )
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
        except (OSError, ValueError) as exc:
            logger.warning("unreadable %s, no agents listed: %s", manifest_path, exc)
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
            commands.append(
                {
                    "name": cmd_file.stem,
                    "description": cls._extract_first_description(content),
                }
            )
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
            if not stripped or stripped.startswith(("#", "<!--")):
                continue
            if stripped.startswith(("- ", "* ")):
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

    @classmethod
    def _render_brief(cls, adapter_name: str, config: dict, data: dict, project_root: str | None = None) -> str:
        sections = []
        header = (
            f"{config['header']}\n"
            f"<!-- @compiled-by: agentfactory-gen -->\n"
            f"<!-- @source: .ai/ -->\n"
            f"<!-- @adapter: {adapter_name} -->\n"
            f"<!-- @recompile: agentfactory-gen brief -->"
        )
        sections.append(header)
        sections.append(_fmt_harness_identity(adapter_name))
        ctx = data.get("project_context", "")
        if ctx:
            fitted = _fit_context_to_budget(ctx, config, project_root=project_root)
            sections.append(f"## Project Context\n\n{fitted}")
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

        adapters_root = Path(project_root) / HARNESS_ROOT / "adapters"
        if not adapters_root.exists():
            return

        data = {
            "skills": cls._collect_skills_data(project_root),
            "agents": cls._collect_agents_data(project_root),
            "commands": cls._collect_commands_data(project_root),
            "rules": cls._collect_rules_data(project_root),
            "project_context": _collect_project_context(project_root),
        }

        for adapter_name, config in _FORMAT_REGISTRY.items():
            adapter_dir = adapters_root / adapter_name
            if not adapter_dir.exists():
                continue
            brief_path = adapter_dir / config["output"]
            try:
                new_content = cls._render_brief(adapter_name, config, data, project_root=str(project_root))
                if brief_path.exists() and brief_path.read_text(encoding="utf-8") == new_content:
                    continue
                brief_path.write_text(new_content, encoding="utf-8")
            except Exception as e:  # noqa: BLE001 - one broken adapter must not stop the others
                logger.warning("Warning: failed to compile brief for %s: %s", adapter_name, e)

        cls._compile_agentfactory_md(project_root, data)

    @classmethod
    def _compile_agentfactory_md(cls, project_root: str, data: dict) -> None:
        """Upsert <!-- @commands-start/end --> and <!-- @rules-start/end --> into AgentFactory.md.

        Uses Claude's formatters (most readable universal markdown) so AgentFactory.md
        becomes a full master brief — same richness as per-adapter compiled briefs.
        Marker blocks are appended if absent, replaced if present.
        """
        af_path = Path(project_root) / HARNESS_ROOT / CONTEXT_FILE
        if not af_path.exists():
            return
        content = af_path.read_text(encoding="utf-8")
        claude_cfg = _FORMAT_REGISTRY["claude"]
        commands_text = _fmt_commands_list(data.get("commands", []), claude_cfg) or ""
        rules_text = _fmt_rules_list(data.get("rules", []), claude_cfg) or ""

        commands_block = f"<!-- @commands-start -->\n{commands_text}\n<!-- @commands-end -->"
        rules_block = f"<!-- @rules-start -->\n{rules_text}\n<!-- @rules-end -->"

        commands_pat = re.compile(r"<!-- @commands-start -->.*?<!-- @commands-end -->", re.DOTALL)
        rules_pat = re.compile(r"<!-- @rules-start -->.*?<!-- @rules-end -->", re.DOTALL)

        if "<!-- @commands-start -->" in content:
            content = commands_pat.sub(commands_block, content)
        else:
            content = content.rstrip() + f"\n\n{commands_block}\n"

        if "<!-- @rules-start -->" in content:
            content = rules_pat.sub(rules_block, content)
        else:
            content = content.rstrip() + f"\n\n{rules_block}\n"

        af_path.write_text(content, encoding="utf-8")

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
