# Issue: Implement Standalone Skill Import (`agent-gen import-skill`)
<!-- version: 1.0.0 -->

## Description
Currently, the `agent-gen import` command is strictly designed to import entire agents as Portable Units (a `.zip` file containing an `agent-manifest.json` and the full 5-directory structure). It does not currently support fetching or importing individual, standalone skills from an external repository or local source. This feature adds the ability to import individual skills into an existing agent.

## Proposed Solution
### 1. Librarian Engine (`agent_gen/librarian.py`)
- Add `import_skill(skill_source: str, target_agent_root: str) -> str`:
    - Detect if `skill_source` is a ZIP or a directory.
    - Validate presence of `skill-manifest.json`.
    - Determine skill name from the source folder or manifest.
    - Copy/Extract into `agents/<target_agent>/skills/<skill_name>/`.
    - Automatically trigger `self.sync()` to update the agent manifest.

### 2. CLI Layer (`agent_gen/cli.py`)
- Add a new command: `agent-gen import-skill <path> --to <agent_name>`:
    - Validate that the target agent exists.
    - Call `librarian.import_skill()`.
    - Provide a success summary similar to the agent import.

## Acceptance Criteria
- [ ] Command `agent-gen import-skill <path> --to <agent_name>` implemented.
- [ ] Supports both ZIP bundles and local directories.
- [ ] Validates `skill-manifest.json` upon import.
- [ ] Automatically syncs the target agent's manifest.
