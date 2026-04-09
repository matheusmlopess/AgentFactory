# test-intel-agent
<!-- version: 1.0.0 -->

AgentFactory-powered agent demonstrating intelligence-layer features: dependency detection and skill manifest parsing.

## Role
Prototype agent used to test the Librarian's AST-based dependency analysis. Contains a search skill with a dependency on `scripts/utils.py`, which the Librarian auto-detects via Python import scanning.

## Skills
- `skills/search.md` — search prompt template
- `skills/search/skill-manifest.json` — skill metadata (type: retrieval)

## Scripts
- `scripts/utils.py` — utility module imported by the search skill (auto-detected dependency)

## Notes
This is a test/demo agent for AgentFactory development. Not intended for production use.
