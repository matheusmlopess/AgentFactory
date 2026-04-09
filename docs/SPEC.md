# AgentFactory Technical Specification
<!-- version: 1.0.0 -->

This document provides a technical specification for LLMs (Claude, Gemini, Codex) and developers to author assets that are fully compatible with the AgentFactory Librarian.

## 1. Directory Structure

Every agent must follow the **5-Directory Standard**:

*   `skills/`: High-level capabilities. Can be flat files or subdirectories.
    *   *Requirement*: Subdirectories should include a `skill-manifest.json`.
*   `commands/`: Documentation for specific CLI or agent commands.
*   `scripts/`: Executable logic (Python, JS, etc.) that the agent can call.
*   `orchestration/`: Workflow definitions and agent entry points.
*   `docs/`: General documentation, including `CLAUDE.md` or `GEMINI.md`.

## 2. Manifest Schema (`agent-manifest.json`)

Located at the root of the agent directory.

```json
{
  "name": "string",
  "version": "semver",
  "description": "string",
  "orchestration_plan": "path/to/entry-point",
  "resources": {
    "skills": ["path/to/file", ...],
    "commands": [...],
    "docs": [...],
    "scripts": [...],
    "orchestration": [...]
  },
  "dependencies": {
    "resource/path": ["dependency/path", ...]
  },
  "skills_metadata": {
    "skills/subdir": { "key": "value" }
  }
}
```

## 3. Intelligence Layer Features

### Automated Dependency Tracking
The Librarian scans text files for explicit dependency annotations. Use the following syntax in Markdown or comments:

```markdown
<!-- @depends-on: scripts/utils.py -->
```

### Skill Manifests (`skill-manifest.json`)
Placed inside `skills/<name>/`. Used to provide metadata about a specific complex skill.

```json
{
  "type": "retrieval | tool | reasoning",
  "requires_api_key": boolean,
  "description": "string"
}
```

## 4. Lifecycle Commands

*   `agent-gen deploy <name>`: Scaffolds the structure.
*   `agent-gen wrap <name>`: Synchronizes, audits, and compresses into a Portable Unit.
*   `agent-gen import <zip>`: Unpacks and registers the agent in the project.
*   `agent-gen audit <name>`: Checks for broken paths, missing manifests, or untracked files.
*   `agent-gen retrofit <path>`: Converts existing Claude/Gemini/Codex structures into AgentFactory.

## 5. Metadata Enforcement
*   **Orchestration**: The Librarian automatically picks the first file in `orchestration/` if `orchestration_plan` is not set.
*   **Validation**: Bundling (wrapping) will fail if any file in the `resources` or `dependencies` lists is missing from the disk.
