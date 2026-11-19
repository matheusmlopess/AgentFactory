"""FormatSwitch: per-adapter brief formats (_FORMAT_REGISTRY) and the formatters that render each section.

Split out of librarian.py (#189); `agent_gen.librarian` re-exports the public names."""

from __future__ import annotations

import os
from pathlib import Path

from .constants import CONTEXT_FILE, HARNESS_ROOT
from .oracle import _run_preamble_oracle

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
        # Per-skill character budget (bytes). Warn if SKILL.md exceeds this.
        "skill_char_limit": 18_000,
        # Completeness score threshold (0-100) for --check-completeness.
        "completeness_threshold": 90,
        # Max chars of AgentFactory.md preamble to inject into this brief.
        "context_char_limit": 4_000,
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
        "config_default": 'model = "gpt-5.4"\n',
        "skill_path_template": ".codex/skills/{name}/SKILL.md",
        "command_prefix": "",
        "sections": {
            "skills": "_fmt_skills_blocks",
            "commands": None,
            "agents": "_fmt_agents_list",
            "rules": "_fmt_rules_list",
        },
        "section_order": ["skills", "agents", "rules"],
        # Codex has a tighter context window — stricter per-skill budget.
        "skill_char_limit": 10_000,
        "completeness_threshold": 95,
        "context_char_limit": 2_000,
    },
    "gemini": {
        "output": "brief.md",
        "header": "# AgentFactory Intelligence Brief — Gemini CLI",
        "root_files": ["GEMINI.md"],
        "folder_symlink": ".gemini",
        "wiring": {
            # Gemini CLI scans .gemini/skills/ (renamed from .gemini/tools/ in 2026 open-standard alignment)
            "skills": "../../skills",
        },
        "config_file": "config.json",
        "config_default": "{}",
        "skill_path_template": ".gemini/skills/{name}/SKILL.md",
        "command_prefix": "",
        "sections": {
            "skills": "_fmt_skills_tools",
            "commands": None,
            "agents": "_fmt_agents_list",
            "rules": "_fmt_rules_list",
        },
        "section_order": ["skills", "agents", "rules"],
        "skill_char_limit": 18_000,
        "completeness_threshold": 90,
        "context_char_limit": 4_000,
    },
    "antigravity": {
        "output": "brief.md",
        "header": "# AgentFactory Intelligence Brief — Antigravity CLI",
        # Antigravity (agy) reads both AGENTS.md and GEMINI.md (GEMINI.md wins when
        # both exist). GEMINI.md is owned by the gemini adapter, so this adapter
        # claims AGENTS.md — the cross-tool open-standard context file. At init,
        # codex (earlier in the registry) wins AGENTS.md; an explicit
        # 'adapter add antigravity' re-points it.
        "root_files": ["AGENTS.md"],
        "folder_symlink": ".agents",
        "wiring": {
            # .agents/skills is the cross-agent open-standard scan path (agentskills.io)
            "skills": "../../skills",
            # Antigravity workspace rules live in .agents/rules/
            "rules": "../../rules",
        },
        "config_file": "mcp_config.json",
        "config_default": '{\n  "mcpServers": {}\n}\n',
        "skill_path_template": ".agents/skills/{name}/SKILL.md",
        "command_prefix": "",
        "sections": {
            "skills": "_fmt_skills_tools",
            "commands": None,
            "agents": "_fmt_agents_list",
            "rules": "_fmt_rules_list",
        },
        "section_order": ["skills", "agents", "rules"],
        "skill_char_limit": 18_000,
        "completeness_threshold": 90,
        "context_char_limit": 4_000,
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
        return "## Available Skills\n\nNo skills imported yet."
    template = config["skill_path_template"]
    blocks = ["## Available Skills"]
    for s in skills:
        path = template.replace("{name}", s["name"])
        trigger_val = s.get("triggers") or s.get("input_hint") or "see skill documentation"
        block = (
            f"### {s['name']}\n"
            f"- Description: {s.get('description', 'No description')}\n"
            f"- Use when: {trigger_val}\n"
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


def _fmt_harness_identity(adapter_name: str) -> str:
    """Universal harness identity block — injected into every adapter brief.

    Tells any AI agent (regardless of which CLI it is running in) that this
    is an AgentFactory project, where the canonical context lives, and how to
    find the briefs for all other adapters. This is the cross-adapter navigation
    header that survives a CLI swap.
    """
    lines = [
        "## Harness",
        "",
        "AgentFactory project. All adapters share the same harness context.",
        "",
        "```",
        f"  Harness root : {HARNESS_ROOT}/",
        f"  This adapter : {adapter_name}",
        "  Recompile    : agentfactory-gen brief",
        "```",
        "",
        "Shared context (read these to understand the project):",
        "",
        f"  {HARNESS_ROOT}/{CONTEXT_FILE:<23} ← project overview + master compiled brief",
        f"  {HARNESS_ROOT}/skills/               ← skill specs (symlinked per adapter)",
        f"  {HARNESS_ROOT}/rules/                ← behavior rules compiled into this brief",
        f"  {HARNESS_ROOT}/agent-manifest.json   ← global agent registry",
        f"  {HARNESS_ROOT}/memory/milestones.md  ← issue and milestone tracking",
        "",
        "All adapter briefs (same project, different CLI):",
        "",
    ]
    for name, cfg in _FORMAT_REGISTRY.items():
        root_files = cfg.get("root_files", [])
        root_display = " / ".join(root_files) if root_files else cfg["output"]
        marker = " ← YOU ARE HERE" if name == adapter_name else ""
        lines.append(f"  {name:<8} {root_display:<20} → {HARNESS_ROOT}/adapters/{name}/{cfg['output']}{marker}")
    lines += [
        "",
        "If switching CLI: run `agentfactory-gen brief` to recompile all active adapter briefs.",
    ]
    return "\n".join(lines)


def _collect_project_context(project_root: str) -> str:
    """Extract the human-written preamble from .ai/AgentFactory.md.

    Returns everything before the first <!-- @ registry marker, with the H1
    title line stripped (it duplicates the adapter brief header).
    """
    af_path = Path(project_root) / HARNESS_ROOT / CONTEXT_FILE
    if not af_path.exists():
        return ""
    content = af_path.read_text(encoding="utf-8")
    marker = content.find("<!-- @")
    preamble = content[:marker].strip() if marker > 0 else content.strip()
    lines = preamble.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _fit_context_to_budget(context: str, adapter_config: dict, project_root: str | None = None) -> str:
    """Truncate preamble to adapter's context_char_limit.

    Truncates at the last paragraph break before the limit. Appends an HTML
    comment warning if truncated. When AGENTFACTORY_LICENSE_KEY is set and
    project_root is provided, runs the completeness oracle and prints the
    delta to stderr (pro gate advisory, non-blocking).
    """
    limit = adapter_config.get("context_char_limit", 4_000)
    if len(context) <= limit:
        return context
    window = context[:limit]
    cut = window.rfind("\n\n")
    if cut < limit // 2:
        cut = limit
    truncated = context[:cut].rstrip()
    original_len = len(context)
    has_key = bool(os.environ.get("AGENTFACTORY_LICENSE_KEY"))
    if has_key and project_root:
        try:
            _run_preamble_oracle(context, truncated, project_root)
        except Exception:
            pass
    completeness_hint = " Run: python3 .ai/scripts/skill-completeness-check.py --context to verify." if has_key else ""
    warning = (
        f"\n\n<!-- ⚠ context truncated: {original_len} → {limit} chars "
        f"for {adapter_config.get('completeness_threshold', 90)}% budget.{completeness_hint} -->"
    )
    return truncated + warning


_FORMATTER_DISPATCH: dict = {
    "_fmt_skills_table": _fmt_skills_table,
    "_fmt_skills_blocks": _fmt_skills_blocks,
    "_fmt_skills_tools": _fmt_skills_tools,
    "_fmt_commands_list": _fmt_commands_list,
    "_fmt_agents_list": _fmt_agents_list,
    "_fmt_rules_list": _fmt_rules_list,
}
