# CLAUDE.md
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
- **Intelligence Layer:** `_detect_dependencies` (AST-based Python import parsing + `<!-- @depends-on: -->` marker discovery) and `_detect_orchestration` for cross-file relationship detection.
- **Retrofit:** `propose_retrofit` heuristically detects Claude/Gemini/Codex layouts and maps them to AgentFactory standard via `CONVERSION_PROFILES`.

Key constants in `librarian.py`:
- `TRACKED_DIRS = ["skills", "commands", "docs", "scripts", "orchestration"]`
- `HARNESS_ROOT = ".ai"` | `MANIFEST_FILE = "agent-manifest.json"`

### CLI (`src/agent_gen/cli.py`)
Thin Click wrappers around the Librarian. Commands: `init`, `deploy`, `describe`, `audit`, `wrap`, `retrofit`, `import`, `import-skill`, `uninstall`. The `--from-git` flag on `import` clones a repo, auto-retrofits, stubs skill manifests, and wraps in one step.

### Multi-CLI Harness
Claude, Codex, and Gemini share the same `.ai/` directory for shared context with no conflicts. Adapter wiring (`_ensure_adapter_wiring`) creates capability symlinks inside each adapter directory.

## Rules
- Every `.md` file must include a `<!-- version: X.Y.Z -->` marker.
- Use semantic commit messages and feature branches; all changes via PR.
- Aim for 80%+ test coverage for new logic; always write a reproduction test for bugs.

## Global Skills
<!-- @skills-registry:start -->
- **diff-visualizer**: Generates HTML diff reports visualizing what changed between two versions of the repo. (See: `.ai/skills/diff-visualizer/SKILL.md`)
- **git-versioning**: Manages project-wide versioning and repo-state.md updates. (See: `.ai/skills/git-versioning/SKILL.md`)
- **issue-tracker**: Regenerates the issue priority report and dependency matrix from live GitHub data. (See: `.ai/skills/issue-tracker/SKILL.md`)
<!-- @skills-registry:end -->

## Registered Agents
<!-- @agent-registry:start -->
- **test-agent**: Manual Description (See: `.ai/agents/test-agent/docs/CLAUDE.md`)
- **test-claude-agent**: AgentFactory-powered agent demonstrating a minimal Claude-native agent layout. (See: `.ai/agents/test-claude-agent/docs/CLAUDE.md`)
- **test-intel-agent**: AgentFactory-powered agent demonstrating intelligence-layer features: dependency detection and skill manifest parsing. (See: `.ai/agents/test-intel-agent/docs/CLAUDE.md`)
<!-- @agent-registry:end -->

<!-- @commands-start -->
## Commands
- `/completeness-check` — <!-- version: 1.0.0 -->
- `/git-workflow` — <!-- version: 1.0.0 -->
<!-- @commands-end -->

<!-- @rules-start -->
## Behavior Rules
- **Quiet Mode:** Prefer quiet flags to reduce output noise.
- **Version Markers:** Every `.md` file MUST have a version marker.
- **Branches:** Create a feature branch for every task.
- **Create at init:** Every project must have `.ai/memory/milestones.md` scaffolded by `agentfactory-gen init`. It is the single source of truth for all issue and work-item tracking.
- **Secrets:** Never log, print, or commit API keys or secrets.
- **Skill Briefing:** Skill metadata used in compiled briefs must stay brief-safe: keep `description` to a short summary line and `triggers` or `when_to_use` to a short invocation hint instead of procedural detail.
- **Coverage:** Aim for 80%+ test coverage for new logic.
<!-- @rules-end -->
