# Feature: Implement Manifest Librarian for Automated State Tracking

**Labels:** `enhancement`, `infrastructure`, `agent-factory`

## Summary

To support the "Agent Factory" model, we need a background service (the **Librarian**) that monitors the creation of agent assets and maintains an `agent-manifest.json` file. This ensures that any agent deployed can be perfectly "wrapped" and "imported" without manual file tracking.

---

## Background

Agents in the factory are **Portable Units** — self-contained bundles of skills, commands, and docs that can be packaged, transported, and dropped into any new environment. The Librarian is the piece of infrastructure that makes portability possible: it is the single source of truth about what every agent contains.

---

## Requirements

### 1. Automatic Registration
Any time an `agent-gen` command creates a file in `/skills`, `/commands`, or `/docs`, the Librarian must log the relative path in `agent-manifest.json`.

### 2. Environment Validation
A `validate` step that checks every path listed in the manifest actually exists on disk before allowing a `wrap`.  Failures must be surfaced clearly with the offending paths listed.

### 3. Metadata Management
Each manifest must track:
- `name` — agent identifier
- `version` — semver string
- `created_at` — ISO-8601 UTC timestamp
- `git_ref` — short SHA of the repo at wrap time (falls back to `"untracked"`)
- `synced_at` — timestamp of the last `sync()` run
- `resources` — categorised file lists (`skills`, `commands`, `docs`)

---

## CLI Commands

### `agent-gen deploy <name>`
- Creates `agents/<name>/{skills,commands,docs}/`
- Initialises `agent-manifest.json` via `Librarian.init()`
- **Output:** ready-to-code agent directory

### `agent-gen wrap <name> [--out DIR]`
1. Runs `Librarian.sync()` to refresh the manifest from disk
2. Runs `Librarian.validate()` — aborts on any missing files
3. Compresses everything into `<name>-v<version>.zip`
- **Output:** portable agent archive

### `agent-gen import <path_to_zip> [--project-root DIR]`
1. Peeks at the embedded manifest to determine agent name
2. Unpacks the bundle into `agents/<name>/`
3. Reads the manifest to place files in the correct local directories
4. **The Handshake:** merges the agent entry into the project's global `agent-manifest.json`
5. Prints a paste-ready **Success Summary** for Claude:

```
============================================================
Librarian: Import Complete.
  Added 3 skill(s), 2 command(s), and 1 doc(s) to your environment.
  You are now configured as the 'Research-Agent' agent.
  Check docs/CLAUDE.md for your new instructions.
============================================================
```

---

## Acceptance Criteria

- [ ] `agent-gen deploy my-agent` produces a correctly-structured directory with a valid manifest
- [ ] `agent-gen wrap my-agent` refuses to proceed if any manifest-listed file is missing
- [ ] `agent-gen wrap my-agent` produces a zip containing the manifest + all resources
- [ ] `agent-gen import my-agent-v1.0.zip` unpacks and registers the agent in the project manifest
- [ ] The Handshake updates the global `agent-manifest.json` without clobbering existing agents
- [ ] `git_ref` is captured at wrap time and preserved through import

---

## Implementation Notes

The Librarian is implemented as a class (`agent_gen/librarian.py`) called by the CLI layer (`agent_gen/cli.py`), keeping it independently testable.  
Install with: `pip install -e .`  
Entry point: `agent-gen`
