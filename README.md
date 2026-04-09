# AgentFactory
<!-- version: 2.0.0 -->

AgentFactory is a lightweight Python-based CLI (`agent-gen`) designed for building, packaging, and deploying AI agents as portable, framework-agnostic units. 

It provides a meta-framework that standardizes agent behavior, context management, and deployment across multiple AI tools simultaneously.

## The Unified AI Harness (v2.0)

AgentFactory utilizes a revolutionary **Unified Folder Strategy**. It allows you to use Claude, Codex, and Gemini simultaneously on the same project without conflicting instructions or redundant files. 

Native CLI structures (like `.claude/` or `.codex/`) are elegantly symlinked to a single, pristine `.ai` equivalent structure at the root:

```text
.
├── core/         # Core context (Architecture, Agents, Domain)
├── rules/        # Enforceable constraints (Security, Testing)
├── commands/     # Execution scripts
├── prompts/      # Normalized prompt layer
├── skills/       # Reusable deep-context workflows
├── agents/       # Persona roles
├── memory/       # Project state
└── adapters/     # Native CLI configurations (symlinked from root)
```

## CLI Reference

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
2. Install dependencies: `pip install -r requirements.txt` (or via `pyproject.toml`).
3. Run `agent-gen --help` to see available commands.

## Architecture & Contributions
See `core/CLAUDE.md` (Architecture) and `core/GEMINI.md` (Domain) for deeper technical insights. Ensure all contributions follow the `rules/` specified in the repository.

## Registered Agents
<!-- @agent-registry:start -->
- **test-agent**: Manual Description (See: `agents/test-agent/docs/CLAUDE.md`)
- **test-claude-agent**: AgentFactory-powered agent: test-claude-agent (See: `agents/test-claude-agent/docs/CLAUDE.md`)
- **test-intel-agent**: AgentFactory-powered agent: test-intel-agent (See: `agents/test-intel-agent/docs/CLAUDE.md`)
<!-- @agent-registry:end -->
