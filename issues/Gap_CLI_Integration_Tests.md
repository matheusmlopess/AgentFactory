# Issue: Implement Integration Tests for CLI Commands

## Description
Currently, the test suite (`tests/test_librarian_intelligence.py`) covers the core Librarian logic, but we lack integration tests for the `agent-gen` CLI itself.

## Gap Analysis
Without CLI tests, commands like `deploy`, `wrap`, `import`, `audit`, and `retrofit` could break due to argument parsing issues, `click` library updates, or unhandled exceptions in `cli.py`, and we wouldn't catch them in CI.

## Proposed Solution
- Add a new test file: `tests/test_cli.py`.
- Use `click.testing.CliRunner` to simulate user commands.
- Implement end-to-end tests for the full lifecycle: `deploy` -> `describe` -> `wrap` -> `import` -> `uninstall`.

## Acceptance Criteria
- [ ] `CliRunner` tests added for all `agent-gen` commands.
- [ ] End-to-end lifecycle test runs successfully in an isolated temporary directory.