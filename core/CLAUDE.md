# Architecture
<!-- version: 2.0.0 -->

## Overview
AgentFactory is a lightweight Python-based CLI (`agent-gen`) for building, packaging, and deploying AI agents as **Portable Units**.

## Unified Folder Strategy
The project now employs a unified directory structure compatible natively with Claude, Codex, and Gemini via symlink adapters:
1. `core/`: Primary context, architecture, and agent registries.
2. `rules/`: Project constraints.
3. `commands/` & `prompts/`: Standardized execution commands.
4. `skills/`: Deep context workflows.
5. `agents/`: Roles and personas.
6. `memory/`: Project and session context.
7. `adapters/`: Native CLI configs (Claude, Codex, Gemini) mapped back to the root via symlinks.

## Core Engine: The Librarian
The Librarian (`agent_gen/librarian.py`) manages:
- **Manifest Integrity:** Validating `agent-manifest.json`.
- **Lifecycle:** Deploy, Audit, Wrap, Import, Retrofit.
- **Intelligence Layer:** Dependency and orchestration detection via AST parsing and marker discovery.

## Multi-CLI Harness
The project utilizes a tiered AI harness to coordinate Claude, Codex, and Gemini, ensuring a shared context window and seamless handoff.

## Global Skills
<!-- @skills-registry:start -->
- **git-versioning**: Manages project-wide versioning and repo-state.md updates. (See: `skills/git-versioning/SKILL.md`)
<!-- @skills-registry:end -->

## Registered Agents
<!-- @agent-registry:start -->
- **test-agent**: Specialized agent for Git workflows, semantic versioning, and project state management. (See: `agents/test-agent/docs/CLAUDE.md`)
- **test-claude-agent**: AgentFactory-powered agent: test-claude-agent (See: `agents/test-claude-agent/docs/CLAUDE.md`)
- **test-intel-agent**: AgentFactory-powered agent: test-intel-agent (See: `agents/test-intel-agent/docs/CLAUDE.md`)
<!-- @agent-registry:end -->
