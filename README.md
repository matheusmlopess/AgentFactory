# AgentFactory
<!-- version: 2.3.2 -->

A lightweight Python CLI (`agent-gen`) for building, packaging, and deploying AI agents as portable, framework-agnostic units.

AgentFactory provides a **Unified AI Harness** — a single `.ai/` directory that lets Claude, Codex, and Gemini work on the same project simultaneously, sharing context without conflicts.

---

## Project Layout

```text
project/
├── CLAUDE.md  → .ai/AgentFactory.md   ← auto-loaded by Claude
├── AGENTS.md  → .ai/AgentFactory.md   ← auto-loaded by Codex  (same file)
├── GEMINI.md  → .ai/AgentFactory.md   ← auto-loaded by Gemini (same file)
├── CODEX.md   → .ai/AgentFactory.md   ← alias (same file)
├── .claude    → .ai/adapters/claude
├── .gemini    → .ai/adapters/gemini
├── .codex     → .ai/adapters/codex
└── .ai/
    ├── AgentFactory.md      ← single source of truth for all CLI instructions
    ├── agent-manifest.json  ← global agent registry
    ├── adapters/            ← per-CLI config + capability symlinks
    │   ├── claude/          settings.json, commands →, skills →
    │   ├── gemini/          config.json, tools → skills
    │   └── codex/           config.toml, prompts → commands
    ├── rules/               ← enforceable project constraints
    ├── commands/            ← Claude slash commands + Codex prompts (unified)
    ├── skills/              ← reusable deep-context workflows + Gemini tools
    ├── agents/              ← deployed agent directories
    └── memory/              ← project state
```

Each agent under `.ai/agents/<name>/` follows the **5-Directory Standard**:
`skills/` · `commands/` · `docs/` · `scripts/` · `orchestration/`

---

## Installation

```bash
pip install -e .
```

Requires Python 3.11+.

---

## CLI Reference

### Setup
```bash
agent-gen init                        # scaffold .ai/ harness + root symlinks
agent-gen init --project-root <path>  # target a different directory
```

### Agent Lifecycle
```bash
agent-gen deploy <name>               # scaffold a new agent
agent-gen describe <name> --desc "…"  # set agent description
agent-gen audit <name>                # check for missing files, broken deps, version drift
agent-gen wrap <name>                 # compress agent into a shareable ZIP (Portable Unit)
agent-gen import <zip>                # unpack ZIP and register agent
agent-gen import --from-git <url>     # clone repo, auto-retrofit, and import in one step
agent-gen uninstall <name>            # remove agent cleanly
```

### Skills & Intelligence
```bash
agent-gen import-skill <path>                  # import skill into root .ai/skills/
agent-gen import-skill <path> --to <agent>     # import into a specific agent
agent-gen retrofit <path>                      # convert Claude/Gemini/Codex layout to AgentFactory standard
```

---

## Key Features

**`--from-git`** — Import any GitHub repo as an agent in one command:
```bash
agent-gen import --from-git https://github.com/user/repo
```
Reads `README.md` and `CLAUDE.md` to extract descriptions, auto-detects and applies the correct retrofit profile, creates `skill-manifest.json` stubs for sub-agents, and registers the result in `.ai/AgentFactory.md`.

**Librarian** (`src/agent_gen/librarian.py`) — core engine behind every lifecycle operation:
- Manifest integrity validation
- AST-based dependency detection (Python imports + `<!-- @depends-on: -->` annotations)
- Skill manifest auto-registration
- Audit: version drift, repo-state staleness, remote URL mismatch

---

## Architecture & Contributing

See `.ai/AgentFactory.md` for architecture, domain context, and project constraints.
See `docs/SPEC.md` for the technical specification (manifest schema, intelligence layer, lifecycle commands).
Contributions should follow the rules in `.ai/rules/`.

---

## Registered Agents
<!-- @agent-registry:start -->
- **test-agent**: Minimal test agent for validating AgentFactory lifecycle operations: deploy, audit, wrap, and imp... (See: `.ai/agents/test-agent/docs/CLAUDE.md`)
- **test-claude-agent**: AgentFactory-powered agent demonstrating a minimal Claude-native agent layout. (See: `.ai/agents/test-claude-agent/docs/CLAUDE.md`)
- **test-intel-agent**: AgentFactory-powered agent demonstrating intelligence-layer features: dependency detection and sk... (See: `.ai/agents/test-intel-agent/docs/CLAUDE.md`)
<!-- @agent-registry:end -->
