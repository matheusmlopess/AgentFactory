# AgentFactory Intelligence Brief — Gemini CLI
<!-- @compiled-by: agentfactory-gen -->
<!-- @source: .ai/ -->
<!-- @adapter: gemini -->
<!-- @recompile: agentfactory-gen brief -->

## Harness

AgentFactory project. All adapters share the same harness context.

```
  Harness root : .ai/
  This adapter : gemini
  Recompile    : agentfactory-gen brief
```

Shared context (read these to understand the project):

  .ai/AgentFactory.md         ← project overview + master compiled brief
  .ai/skills/               ← skill specs (symlinked per adapter)
  .ai/rules/                ← behavior rules compiled into this brief
  .ai/agent-manifest.json   ← global agent registry
  .ai/memory/milestones.md  ← issue and milestone tracking

All adapter briefs (same project, different CLI):

  claude   CLAUDE.md            → .ai/adapters/claude/brief.md
  codex    AGENTS.md / CODEX.md → .ai/adapters/codex/brief.md
  gemini   GEMINI.md            → .ai/adapters/gemini/brief.md ← YOU ARE HERE

If switching CLI: run `agentfactory-gen brief` to recompile all active adapter briefs.

## Project Context

<!-- version: 2.1.0 -->

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview
AgentFactory is a lightweight Python-based CLI (`agentfactory-gen`) for building, packaging, and deploying AI agents as **Portable Units**. Source lives in `src/agent_gen/`; tests in `src/tests/`.

## Development Commands

```bash
# Install (editable)
pip install -e .

# Run all tests
pytest

# Run a single test file
pytest src/tests/test_cli.py

# Run a single test by name
pytest src/tests/test_cli.py::TestCliCommands::test_e2e_lifecycle
```

## Architecture

### Unified Harness (`.ai/`)
All harness content lives under `.ai/`. Root files are symlinks:
- `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `CODEX.md` → `.ai/AgentFactory.md` (this file)
- `.claude` → `.ai/adapters/claude` | `.gemini` → `.ai/adapters/gemini` | `.codex` → `.ai/adapters/codex`

Internal layout:
1. `.ai/rules/`: Enforceable project constraints (git, testing, docs, cli, security).
2. `.ai/commands/`: Slash commands (Claude) and prompt templates (Codex).
3. `.ai/skills/`: Reusable deep-context workflows. Accessible to Claude via `.claude/skills/`.
4. `.ai/agents/`: Deployed agent directories — each follows the **5-Directory Standard**: `skills/` · `commands/` · `docs/` · `scripts/` · `orchestration/`.
5. `.ai/memory/`: Project state and context.
6. `.ai/adapters/`: Per-CLI config + capability symlinks (commands→, skills→, tools→).

### Core Engine: The Librarian (`src/agent_gen/librarian.py`)
Central class driving every lifecycle operation. Key responsibilities:
- **Manifest Integrity:** Load/validate/save `agent-manifest.json` per agent.
- **Lifecycle:** `init`, `sync`, `audit`, `wrap`, `unpack`, `import_skill`, `migrate` (retrofit), `uninstall`.
- **Global registry:** `sync_to_global`, `register_in_project`, `update_harness_files` keep `.ai/AgentFactory.md` and `.ai/agent-manifest.json` in sync across all agents.
- **Intelligence Layer:** `_detect_dependencies` (AST-based Python import parsing + `

## Available Tools

### diff-visualizer
- Description: Generates HTML diff reports visualizing what changed between two versions of the repo.
- Input: see tool documentation
- See: .gemini/tools/diff-visualizer/SKILL.md

### git-versioning
- Description: Manages project-wide versioning and repo-state.md updates.
- Input: see tool documentation
- See: .gemini/tools/git-versioning/SKILL.md

### issue-tracker
- Description: Regenerates the issue priority report and dependency matrix from live GitHub data.
- Input: see tool documentation
- See: .gemini/tools/issue-tracker/SKILL.md

## Registered Agents
- **test-agent**: Manual Description
- **test-intel-agent**: AgentFactory-powered agent demonstrating intelligence-layer features: dependency detection and skill manifest parsing.
- **test-claude-agent**: AgentFactory-powered agent demonstrating a minimal Claude-native agent layout.

## Behavior Rules
- **Quiet Mode:** Prefer quiet flags to reduce output noise.
- **Version Markers:** Every `.md` file MUST have a version marker.
- **Branches:** Create a feature branch for every task.
- **Create at init:** Every project must have `.ai/memory/milestones.md` scaffolded by `agentfactory-gen init`. It is the single source of truth for all issue and work-item tracking.
- **Secrets:** Never log, print, or commit API keys or secrets.
- **Skill Briefing:** Skill metadata used in compiled briefs must stay brief-safe: keep `description` to a short summary line and `triggers` or `when_to_use` to a short invocation hint instead of procedural detail.
- **Coverage:** Aim for 80%+ test coverage for new logic.
