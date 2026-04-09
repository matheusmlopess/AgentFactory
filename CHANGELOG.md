# Changelog

## [v2.0.0] - 2026-04-08

### Added
- **Unified AI Harness:** Completely restructured the project root to support an elegant, symlink-based adapter pattern. Claude, Codex, and Gemini now read from a single, unified source of truth (`core/`, `skills/`, `rules/`, etc.) while their native configuration needs are handled transparently via `adapters/`.
- **Standalone Skill Import:** Added `agent-gen import-skill <path> --to <agent>` command to import individual skills (both directories and ZIPs) without requiring a full agent bundle.
- **E2E Integration Tests:** Added `tests/test_cli.py` using `click.testing.CliRunner` to ensure the entire agent lifecycle works seamlessly.
- **Canonical Retrofit Parsing:** Updated the Librarian's heuristics to automatically detect and map the exact canonical folder structures of Claude Code CLI, OpenAI Codex CLI, and Gemini CLI.

### Changed
- **Librarian Refactor:** The Librarian `update_harness_files` is now completely symlink-aware, preventing accidental duplication or overwriting of root symlinks. It targets the pristine `core/` structure directly.
- **Token Budgets:** Added a `budget_check.py` script to ensure core architectural files don't exceed the token boundaries set in `ai/harness.json`.

### Fixed
- Fixed an issue where deeply nested directories would crash `shutil.move` during the `retrofit` execution.
- Added ephemeral harness paths (caches, histories, local settings) from all 3 CLIs to `.gitignore`.
