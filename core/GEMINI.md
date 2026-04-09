# Domain
<!-- version: 2.0.0 -->

## Project: AgentFactory
AgentFactory is a meta-framework for AI agents. It treats agents not just as prompts, but as structured, versioned, and portable software artifacts.

## Key Concepts
- **Portable Units:** Self-contained ZIP packages containing all logic and instructions for an agent.
- **Retrofitting:** The process of converting legacy or non-standard agent structures into the AgentFactory 5-Directory Standard.
- **Intelligence Layer:** Automated discovery of agent dependencies using `<!-- @depends-on: ... -->` markers.
- **Handshake Protocol:** The validation process performed by the Librarian when importing a new agent.

## Registered Agents
<!-- @agent-registry:start -->
- **test-agent**: Specialized agent for Git workflows, semantic versioning, and project state management. (See: `agents/test-agent/docs/CLAUDE.md`)
- **test-claude-agent**: AgentFactory-powered agent: test-claude-agent (See: `agents/test-claude-agent/docs/CLAUDE.md`)
- **test-intel-agent**: AgentFactory-powered agent: test-intel-agent (See: `agents/test-intel-agent/docs/CLAUDE.md`)
<!-- @agent-registry:end -->
