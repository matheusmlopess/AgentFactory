# Issue: Agent-as-a-Tool (Exchange & Repository)

**Status**: Future Roadmap
**Priority**: Medium

## Description
Enable agents to autonomously discover and exchange skills and agents via tool calls. This is the foundation for a centralized "Agent Repository."

## Requirements
1. **Exchange Tool**: A new command/tool that allows an agent to "send" a Portable Unit (.zip) to another project or agent.
2. **Discovery Mechanism**: Integration with a remote or local repository to search for agents by name or description (fetched from `agent-manifest.json`).
3. **Automated Resorting**: A system where the Librarian can automatically re-index and "resort" agents based on their dependencies and tags.

## Proposed Workflow
- Agent A calls `get_skill("web-search")`.
- Librarian checks local manifest; if not found, it queries the Repository.
- Librarian downloads the Portable Unit and runs `agent-gen import` automatically.

## Acceptance Criteria
- [ ] Design document for the Tool-Call Exchange protocol.
- [ ] Prototype of a `fetch-agent` tool that interfaces with a dummy repository.
