# Implementation Plan: Gemini CLI Alignment

## Objective
Align the `AgentFactory.old` repository with Gemini CLI standards using a "Backward-Compatible Bridge" strategy. This ensures native Gemini functionality (skills, settings, slash commands) while preserving existing `AgentFactory` logic and tests.

## Key Files & Context
- `src/agent_gen/librarian.py`: Central logic for adapter wiring and brief compilation.
- `.ai/adapters/gemini/`: The Gemini adapter directory (symlinked to `.gemini`).
- `.ai/scripts/harness-doctor.sh`: Health check script.
- `GEMINI.md`: AI instruction brief for Gemini.

## Implementation Steps

### Phase 1: Update Librarian.py logic
1.  **Modify `_FORMAT_REGISTRY["gemini"]`:**
    - Set `config_file` to `"settings.json"`.
    - Update `wiring` to include `"skills": "../../skills"`, `"tools": "../../skills"`, and `"commands": "../../commands"`.
    - Update `skill_path_template` to use `.gemini/skills/...`.
    - Set `command_prefix` to `"/"`.
    - Add `"commands"` to `sections` and `section_order`.
2.  **Modify `CONVERSION_PROFILES["gemini"]`:**
    - Ensure it matches the modern layout: `".gemini/skills": "skills"`, `".gemini/commands": "commands"`.

### Phase 2: Structural Bridge & Regeneration
1.  **Rename Legacy Config:** Rename `.ai/adapters/gemini/config.json` to `.ai/adapters/gemini/settings.json`.
2.  **Regenerate Harness:** Run `python3 -m agent_gen.cli brief` (or equivalent `agentfactory-gen brief`) to:
    - Create the new symlinks (`skills`, `tools`, `commands`) in `.ai/adapters/gemini/`.
    - Recompile `GEMINI.md` (brief.md) with updated paths and command list.
3.  **Bridge MCP Servers:** Manually inject any existing MCP configuration from `.mcp.json` into the new `.ai/adapters/gemini/settings.json`.

### Phase 3: Script & Health Check Calibration
1.  **Update `harness-doctor.sh`:**
    - Modify `check_adapter_wiring` to accept either `tools` or `skills` for Gemini, or specifically check for the bridge symlinks.
2.  **Create Example Native Command:**
    - Create a sample `.toml` command in `.ai/commands/` (e.g., `doctor.toml`) to verify slash command functionality in Gemini.

## Verification & Testing
1.  **Harness Health:** Run `./.ai/scripts/harness-doctor.sh` and ensure it passes (Exit 0).
2.  **Structural Audit:** Verify `.gemini/skills`, `.gemini/tools`, and `.gemini/commands` all exist and point to the correct internal `.ai/` paths.
3.  **Brief Audit:** Verify `GEMINI.md` references `.gemini/skills/` and includes a `## Commands` section with `/` prefixes.
4.  **CLI Verification:** (If possible) Start a Gemini CLI session and verify:
    - `/skills list` shows the imported skills.
    - Custom slash commands are recognized.
