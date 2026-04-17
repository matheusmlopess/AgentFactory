# AgentFactory Intelligence Brief — Claude Code
<!-- @compiled-by: agentfactory-gen -->
<!-- @source: .ai/ -->
<!-- @adapter: claude -->
<!-- @recompile: agentfactory-gen brief -->

## Harness

AgentFactory project. All adapters share the same harness context.

```
  Harness root : .ai/
  This adapter : claude
  Recompile    : agentfactory-gen brief
```

Shared context (read these to understand the project):

  .ai/skills/               ← skill specs (symlinked per adapter)
  .ai/rules/                ← behavior rules compiled into this brief
  .ai/agent-manifest.json   ← global agent registry
  .ai/memory/milestones.md  ← issue and milestone tracking

All adapter briefs (same project, different CLI):

  claude   CLAUDE.md            → .ai/adapters/claude/brief.md ← YOU ARE HERE
  codex    AGENTS.md / CODEX.md → .ai/adapters/codex/brief.md
  gemini   GEMINI.md            → .ai/adapters/gemini/brief.md

If switching CLI: run `agentfactory-gen brief` to recompile all active adapter briefs.

## Available Skills

| Skill | When to invoke | Path |
|-------|----------------|------|
| diff-visualizer |  | `.claude/skills/diff-visualizer/SKILL.md` |
| git-versioning |  | `.claude/skills/git-versioning/SKILL.md` |
| issue-tracker |  | `.claude/skills/issue-tracker/SKILL.md` |

## Commands
- `/git-workflow` — <!-- version: 1.0.0 -->

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
