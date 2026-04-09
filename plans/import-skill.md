# Implementation Plan: Standalone Skill Import (`agent-gen import-skill`)
<!-- version: 1.0.0 -->

## Objective
Enable users to import standalone skills (as ZIP files or directories) directly into an existing agent's `skills/` directory, expanding the Librarian's capability beyond full-agent imports.

## Proposed Changes

### 1. Librarian Engine (`agent_gen/librarian.py`)
- Add `import_skill(skill_source: str, target_agent_root: str) -> str`:
    - Detect if `skill_source` is a ZIP or a directory.
    - Validate presence of `skill-manifest.json` (or common skill files if simple).
    - Determine skill name from the source folder or manifest.
    - Copy/Extract into `agents/<target_agent>/skills/<skill_name>/`.
    - Automatically trigger `self.sync()` to update the agent manifest.

### 2. CLI Layer (`agent_gen/cli.py`)
- Add a new command: `agent-gen import-skill <path> --to <agent_name>`:
    - Validate that the target agent exists.
    - Call `librarian.import_skill()`.
    - Provide a success summary similar to the agent import.

### 3. Verification & Testing
- Create `tests/test_librarian_skills.py`.
- Test importing a skill from a ZIP.
- Test importing a skill from a local directory.
- Verify that `agent-manifest.json` is correctly updated after the import.
- Verify that `agent-gen audit` passes for the agent after the skill import.

## GitHub Issue Draft
**Title:** Feature: Implement Standalone Skill Import (`agent-gen import-skill`)
**Description:** 
Currently, the `agent-gen import` command only handles entire agents. This feature adds the ability to import individual skills into an existing agent.
**Acceptance Criteria:**
- [ ] Command `agent-gen import-skill <path> --to <agent_name>` implemented.
- [ ] Supports both ZIP bundles and local directories.
- [ ] Validates `skill-manifest.json` upon import.
- [ ] Automatically syncs the target agent's manifest.
