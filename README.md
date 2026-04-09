# AgentFactory
<!-- version: 2.0.0 -->

AgentFactory is a lightweight Python-based CLI (`agent-gen`) designed for building, packaging, and deploying AI agents as portable, framework-agnostic units. 

It provides a meta-framework that standardizes agent behavior, context management, and deployment across multiple AI tools simultaneously.

## The Unified AI Harness (v2.0)

AgentFactory utilizes a **Unified Folder Strategy**. It allows you to use Claude, Codex, and Gemini simultaneously on the same project without conflicting instructions or redundant files.

All harness content lives inside a single `.ai/` directory. The project root stays clean — only three required instruction files (auto-loaded by each CLI) and three hidden native CLI symlinks are exposed:

```text
project/
├── CLAUDE.md → .ai/.CLAUDE.md    ← auto-loaded by Claude
├── AGENTS.md → .ai/.CLAUDE.md    ← auto-loaded by Codex  (same file)
├── GEMINI.md → .ai/.CLAUDE.md    ← auto-loaded by Gemini (same file)
├── .claude   → .ai/adapters/claude
├── .gemini   → .ai/adapters/gemini
├── .codex    → .ai/adapters/codex
└── .ai/
    ├── .CLAUDE.md       # single source of truth for all CLI instructions
    ├── agent-manifest.json
    ├── adapters/        # per-CLI config + capability symlinks
    ├── rules/           # enforceable constraints
    ├── commands/        # Claude slash commands + Codex prompts (unified)
    ├── skills/          # reusable deep-context workflows + Gemini tools
    ├── agents/          # deployed agent directories
    └── memory/          # project state
```

## CLI Reference

### Project Setup
- `agent-gen init`: Initialize the AgentFactory harness in a new or existing project — creates `.ai/` structure, root symlinks, and adapter wiring.

### Agent Lifecycle
- `agent-gen deploy <name>`: Scaffold a new agent.
- `agent-gen audit <name>`: Check agent for missing files or broken dependencies.
- `agent-gen wrap <name>`: Compress agent into a shareable ZIP package.
- `agent-gen import <zip>`: Unpack a ZIP and register the agent in your project.
- `agent-gen uninstall <name>`: Remove an agent cleanly.

### Intelligence & Retrofitting
- `agent-gen retrofit <path>`: Ingest an existing agent folder and automatically standardize it to the AgentFactory format using heuristic parsing of canonical Claude, Codex, and Gemini structures.
- `agent-gen import-skill <path> --to <agent>`: Import a standalone skill (ZIP or directory) directly into an existing agent.

## Installation & Setup

1. Install Python 3.11+.
2. Install: `pip install -e .`
3. Run `agent-gen init` to scaffold the harness in your project.
4. Run `agent-gen --help` to see all available commands.

## Architecture & Contributions
See `.ai/.CLAUDE.md` for architecture, domain context, and project constraints. Contributions should follow the rules defined in `.ai/rules/`.

## Registered Agents
<!-- @agent-registry:start -->
- **test-agent**: Manual Description (See: `agents/test-agent/docs/CLAUDE.md`)
- **test-claude-agent**: AgentFactory-powered agent: test-claude-agent (See: `agents/test-claude-agent/docs/CLAUDE.md`)
- **test-intel-agent**: AgentFactory-powered agent: test-intel-agent (See: `agents/test-intel-agent/docs/CLAUDE.md`)
<!-- @agent-registry:end -->
