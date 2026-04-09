# Fix Multi-CLI Harness Gaps

## Problem
Several architectural gaps exist in the current harness:
1. Librarian is not symlink-aware and may corrupt consolidated root files.
2. Missing `.gitignore` entries for ephemeral harness data.
3. Missing shared `.mcp.json` at the root.

## Objective
Refactor the Librarian to be symlink-aware, update Git exclusions, and create the shared MCP configuration.

## Requirements
- Librarian must update `ai/shared/AGENTS.md` instead of root symlinks.
- `.gitignore` must exclude `ai/*/history/` and `ai/*/cache/`.
- Root `.mcp.json` must be created.
