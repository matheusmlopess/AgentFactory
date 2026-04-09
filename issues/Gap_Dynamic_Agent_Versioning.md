# Issue: Add Version Management Command (`agent-gen bump`)
<!-- version: 1.0.0 -->

## Description
Agent versions are currently hardcoded to `"version": "1.0.0"` in `Librarian.init()`. 

## Gap Analysis
As developers iterate on their agents, there is no CLI-native way to bump the version. Users have to manually edit the `agent-manifest.json` to change the version, which is error-prone and undermines the CLI-first lifecycle.

## Proposed Solution
- Add a new command: `agent-gen bump <name> [major|minor|patch]`.
- This command should increment the version string in `agent-manifest.json` according to semantic versioning (SemVer) rules.
- Automatically run `librarian.sync()` after bumping to keep timestamps and hashes accurate.

## Acceptance Criteria
- [ ] `bump` command added to `cli.py`.
- [ ] Correctly parses and increments SemVer strings.
- [ ] Updates `agent-manifest.json` safely.