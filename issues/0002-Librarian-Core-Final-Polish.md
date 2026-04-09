# Issue: Librarian Core Final Polish

**Status**: Planned
**Priority**: High

## Description
To ensure the AgentFactory is production-ready, we need to address critical lifecycle gaps in the Librarian engine.

## Tasks
1. **`agent-gen uninstall <name>`**: 
    - Implement the `uninstall` command in `cli.py`.
    - Librarian must remove the agent directory from `agents/`.
    - Librarian must remove the agent entry from the project-level `agent-manifest.json`.
2. **Advanced Python Dependency Scanning**:
    - Update `_analyze_dependencies` in `librarian.py`.
    - Parse `import x` or `from x import y`.
    - If `x.py` exists in `scripts/`, automatically add it to the dependency graph.
3. **Pre-Import Audit**:
    - Update `import_agent` in `cli.py`.
    - Run `librarian.audit()` on the extracted contents in a temporary location before final placement.
    - Abort the import if the audit fails (broken paths or missing internal dependencies).

## Acceptance Criteria
- [ ] `agent-gen uninstall` cleanly removes all traces of an agent.
- [ ] Python scripts automatically link to their local script dependencies in the manifest.
- [ ] Broken ZIP files are rejected during the import process.
