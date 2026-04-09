# Issue: Context-Aware Agent Acknowledgement

**Status**: Future Roadmap
**Priority**: Medium

## Description
Agents should be "acknowledged" by the environment immediately upon import. This means updating project-wide documentation so that LLMs like Claude, Gemini, and Codex are aware of the new capabilities.

## Requirements
1. **Target Files**: `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` at the project root.
2. **Automated Injection**: 
    - Upon `agent-gen import`, the Librarian should append or update a section in these files.
    - Section should list the agent name, primary description, and a link to its `docs/` or `skills/`.
3. **Deduplication**: Ensure multiple imports don't result in duplicate entries.

## Proposed Syntax for Injection
```markdown
<!-- @agent-registry:start -->
- **[Agent Name]**: [Description] (See: agents/[name]/docs/CLAUDE.md)
<!-- @agent-registry:end -->
```

## Acceptance Criteria
- [ ] Importing an agent updates `CLAUDE.md` and `GEMINI.md` with the new agent's details.
- [ ] Re-importing or updating an agent correctly replaces its existing entry.
