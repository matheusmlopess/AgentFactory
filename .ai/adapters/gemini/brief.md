# AgentFactory Intelligence Brief — Gemini CLI
<!-- @compiled-by: agentfactory-gen -->
<!-- @source: .ai/ -->
<!-- @adapter: gemini -->
<!-- @recompile: agentfactory-gen brief -->

## Available Tools

### diff-visualizer
- Description: Generates HTML diff reports visualizing what changed between two versions of the repo.
- Input: see tool documentation
- See: .gemini/tools/diff-visualizer/SKILL.md

### git-versioning
- Description: Manages project-wide versioning and repo-state.md updates.
- Input: see tool documentation
- See: .gemini/tools/git-versioning/SKILL.md

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
