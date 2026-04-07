# AgentFactory Context (v1.1)

## Project Overview
AgentFactory is a lightweight Python-based CLI (`agent-gen`) for building, packaging, and deploying AI agents as **Portable Units**. 

The **Librarian** (in `agent_gen/librarian.py`) is the engine for manifest integrity, lifecycle management, and a newly implemented **Intelligence Layer** for dependency and orchestration detection.

### Key Technologies
- **Python 3.11+**, **Click** (CLI), **ZIP** packaging, **JSON** manifests.

## The Idealized Architecture
- **5-Directory Standard**: `skills/`, `commands/`, `docs/`, `scripts/` (logic), and `orchestration/` (workflows).
- **Intelligent Manifests**: `agent-manifest.json` tracks metadata (`description`, `orchestration_plan`), automated `dependencies`, and `skills_metadata`.
- **Interoperability**: The `retrofit` command converts existing Claude, Gemini, and Codex structures into AgentFactory units.

## Key Workflows
### Lifecycle
- **Deploy**: `agent-gen deploy <name>` (scaffolds the 5-dir structure).
- **Audit**: `agent-gen audit <name>` (checks for integrity drift and broken dependencies).
- **Wrap**: `agent-gen wrap <name>` (syncs, audits, and compresses).
- **Import**: `agent-gen import <zip>` (unpacks and performs the Handshake).
- **Retrofit**: `agent-gen retrofit <path>` (ingests and standardizes existing agents).

## Intelligence Features
- **Dependency Tracking**: Use `<!-- @depends-on: ... -->` in Markdown or scripts to build a dependency graph.
- **Orchestration Detection**: Automatic entry-point discovery in the `orchestration/` directory.
- **Skill Metadata**: Automatic parsing of `skill-manifest.json` within skill subdirectories.

## Operational Mandates
- **Issue-First Planning**: Every new feature or significant change MUST be documented as an issue in the `issues/` directory AND pushed as a GitHub issue before implementation begins.
- **Plan Mode Requirement**: For complex changes, use `enter_plan_mode` to draft a design document and obtain user approval. Once the plan is approved, it must be converted into a GitHub issue.
- **Interoperability**: Adhere to the `SPEC.md` when authoring new agent assets to ensure Librarian compatibility.

## Future Roadmap
- **Context Awareness**: Automated injection of agent availability into `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` upon import.
- **Tool-Call Exchange**: Enabling agents to fetch and swap skills/agents via direct tool calls (Agent-as-a-Service).
- **Automated Repository**: Integration with a central repository for autonomous agent "resorting" and discovery.

## Registered Agents
<!-- @agent-registry:start -->
- **test-agent**: No description provided. (See: `agents/test-agent/docs/CLAUDE.md`)
<!-- @agent-registry:end -->
