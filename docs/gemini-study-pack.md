# Gemini CLI Study Pack: AgentFactory Alignment

This study pack outlines the strategy for aligning the `AgentFactory.old` repository with the modern Gemini CLI standards while maintaining full backward compatibility with the existing `AgentFactory` ecosystem.

## 1. Context: The Current Disconnect
The current `AgentFactory` implementation for Gemini uses a legacy/non-standard layout within its adapter:
- **Config:** Uses `config.json` instead of `settings.json`.
- **Skills:** Symlinks `.ai/skills` to `.gemini/tools` instead of `.gemini/skills`.
- **Commands:** Lacks a `.gemini/commands` directory for native slash commands.

## 2. The Bridge Strategy: "Convention & Compatibility"
Instead of a destructive migration, we will implement a **Backward-Compatible Bridge**. This satisfies both the Gemini CLI's expectations and the internal `AgentFactory` logic.

### Structural Bridge (Symlinks)
We will maintain the existing directory structure but add dual-purpose symlinks:
- `.gemini/skills` → `../../skills` (Gemini CLI Native)
- `.gemini/tools` → `../../skills` (AgentFactory Legacy)

### Configuration Bridge (Shadowing)
We will transition to `settings.json` but keep `config.json` as a "shadow" or symlink if required by existing scripts, though ideally, `librarian.py` will be updated to prioritize `settings.json`.

### MCP & Commands Bridge
- **MCP:** Map `mcpServers` from `.mcp.json` into `.gemini/settings.json`.
- **Commands:** Create `.gemini/commands/` as a symlink or managed directory to enable native slash commands.

## 3. Implementation Steps (Phased)

### Phase 1: Update Librarian logic
Update `_FORMAT_REGISTRY` in `src/agent_gen/librarian.py` to:
- Change `wiring` from `"tools": "../../skills"` to `"skills": "../../skills"`.
- Add `"tools": "../../skills"` to maintaining backward compatibility.
- Change `config_file` to `settings.json`.
- Update `skill_path_template`.

### Phase 2: Structural Alignment
- Run `agentfactory-gen brief` (which calls `Librarian._ensure_adapter_wiring`) to regenerate symlinks.
- Manually create/manage `.gemini/commands` wiring.

### Phase 3: Script Calibration
Update `harness-doctor.sh` to recognize BOTH `skills/` and `tools/` as valid for Gemini, preventing health-check failures.

## 4. Scenario: The "CLI Swap" Workflow
```text
┌─────────────────────────┐      ┌──────────────────────────┐      ┌─────────────────────────┐
│ 1. User switches to     │─────▶│ 2. Gemini CLI finds      │─────▶│ 3. Gemini CLI loads     │
│    Gemini CLI           │      │    .gemini/settings.json │      │    native .toml cmds    │
└─────────────────────────┘      └──────────────────────────┘      └─────────────────────────┘
                                              │                                 │
                                              ▼                                 ▼
                                 ┌──────────────────────────┐      ┌─────────────────────────┐
                                 │ SUCCESS: .gemini/skills  │      │ SUCCESS: Slash commands │
                                 │ is found via symlink     │      │ work via .toml files    │
                                 └──────────────────────────┘      └─────────────────────────┘
```

---

## 5. Issue Matrix (Bridge Focus)

| ID | Issue | Severity | Status | Bridge Solution |
|:---|:---|:---|:---|:---|
| B-01 | Skill Path | Critical | 🔴 Pending | Dual symlinks (`skills/` and `tools/`) |
| B-02 | Config Name | Major | 🔴 Pending | Migrate `config.json` -> `settings.json` |
| B-03 | Command Logic | Major | 🔴 Pending | Create `.gemini/commands` wiring |
| B-04 | Health Check | Major | 🔴 Pending | Update `harness-doctor.sh` for dual-path |
| B-05 | MCP Servers | Minor | 🔴 Pending | Inject `.mcp.json` into `settings.json` |
