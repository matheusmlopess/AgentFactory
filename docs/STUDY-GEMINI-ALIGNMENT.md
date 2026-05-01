# Study: Gemini CLI Alignment
<!-- version: 1.0.0 -->

This study captures the current Gemini adapter state in `AgentFactory.old`, the
conflicting enforcement points inside the repository, and the concrete
backward-compatible bridge plan required to align the project with modern Gemini
CLI conventions.

## Summary

The repository currently has an internal Gemini inconsistency:

- retrofit logic already expects `.gemini/skills/`
- active adapter wiring still creates `.gemini/tools/`
- generated Gemini config is still `config.json`
- Gemini-native slash commands are not generated as `.toml` files
- project MCP config lives in `.mcp.json`, but Gemini CLI expects `mcpServers`
  inside `.gemini/settings.json`

The recommended fix is a **Backward-Compatible Bridge**:

- make `.gemini/skills/` canonical
- keep `.gemini/tools/` as a compatibility symlink
- make `.gemini/settings.json` canonical
- keep `config.json` only as a legacy bridge artifact
- generate Gemini-native `.gemini/commands/*.toml`
- project `mcpServers` from `.mcp.json` into `settings.json`

## The Current Enforcement Points

The current Gemini behavior is not just a docs problem. It is enforced in
multiple places inside the repository.

### 1. Generation Logic

Primary source:
- `src/agent_gen/librarian.py`

This is the main enforcement layer because it defines what `agentfactory-gen init`,
`adapter add`, and `brief` will generate for Gemini.

Current Gemini registry shape:

```text
_FORMAT_REGISTRY["gemini"]
├─ folder_symlink      = ".gemini"
├─ wiring.tools        = "../../skills"
├─ config_file         = "config.json"
└─ skill_path_template = ".gemini/tools/{name}/SKILL.md"
```

This means the repository currently **creates and reinforces the legacy layout**:

- `.gemini/tools/`
- `.gemini/config.json`
- brief references to `.gemini/tools/...`

### 2. Health Check Validation

Primary source:
- `.ai/scripts/harness-doctor.sh`

The health check currently hardcodes the legacy Gemini expectation:

```text
check_adapter_wiring()
├─ adapters/claude/commands
├─ adapters/claude/skills
├─ adapters/gemini/tools
└─ adapters/codex/prompts
```

This means that even if the repo is manually corrected to `.gemini/skills/`,
the project can still report a harness violation unless the doctor script is
updated at the same time.

### 3. Retrofit Conversion Profile

Primary source:
- `src/agent_gen/librarian.py`

Current retrofit behavior already points toward the modern Gemini structure:

```text
CONVERSION_PROFILES["gemini"]
├─ .gemini/skills     -> skills
├─ .gemini/extensions -> skills/extensions
├─ GEMINI.md          -> docs/GEMINI.md
└─ AGENTS.md          -> orchestration/AGENTS.md
```

This creates an internal contradiction:

- **creation path** uses `tools`
- **validation path** expects `tools`
- **retrofit path** already expects `skills`

### 4. Test Surface

The repository’s test suite reinforces the active adapter contract. Current
tests explicitly assert Gemini behavior around:

- `.ai/adapters/gemini/tools`
- `config.json`
- `## Available Tools`
- `.gemini/tools/.../SKILL.md`
- absence of a Gemini commands section

So any implementation must update:

- generation logic
- validation logic
- existing Gemini tests

or the change will remain inconsistent.

## Visual: Why The Repo Is Conflicted

```text
┌──────────────────────────── Gemini Alignment Conflict ────────────────────────────┐
│ Retrofit says:      .gemini/skills/                                               │
│ Generator says:     .gemini/tools/                                                │
│ Doctor says:        .gemini/tools/ must exist                                     │
│ Gemini CLI docs say:                                                            │
│   ├─ .gemini/settings.json                                                        │
│   ├─ .gemini/skills/                                                              │
│   ├─ .gemini/commands/*.toml                                                      │
│   └─ mcpServers inside settings.json                                              │
│                                                                                  │
│ Result: AgentFactory can claim Gemini support, but the active layout is not      │
│ natively aligned to Gemini CLI conventions.                                       │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Bridge Plan

### Phase 1. Canonical Gemini contract

Move the repository’s intended Gemini target to:

- `.gemini/settings.json`
- `.gemini/skills/`
- `.gemini/commands/*.toml`
- `mcpServers` inside `settings.json`
- `GEMINI.md` remains the root context file

### Phase 2. Compatibility bridge

Keep these compatibility artifacts during migration:

- `.gemini/tools -> ../../skills`
- `config.json` retained only as a legacy bridge artifact

Do **not** keep `tools` or `config.json` as the long-term canonical contract.

### Phase 3. Command bridge

Do not symlink `.ai/commands/*.md` directly into Gemini.

Instead, generate Gemini-native TOML command files for supported shared commands:

- `/completeness-check`
- `/git-workflow`

This is necessary because:

- `.ai/commands/*.md` are shared authoring docs
- Gemini CLI expects `.toml` command definitions

### Phase 4. MCP bridge

Use `.mcp.json` as the project-local source, but project its `mcpServers` into:

- `.gemini/settings.json`

This should be automated, not handled manually.

### Phase 5. Doctor and test alignment

Update the doctor script and Gemini tests to recognize the bridge model:

- canonical `skills`
- compatibility `tools`
- canonical `settings.json`
- optional legacy `config.json`
- generated Gemini TOML commands

## Recommended Implementation Steps

### 1. Update `src/agent_gen/librarian.py`

In `_FORMAT_REGISTRY["gemini"]`:

- set `config_file` to `settings.json`
- add `skills -> ../../skills`
- keep `tools -> ../../skills`
- update `skill_path_template` to `.gemini/skills/{name}/SKILL.md`
- set `command_prefix` to `/`
- add a Gemini commands section back into the brief

In `CONVERSION_PROFILES["gemini"]`:

- keep `.gemini/skills -> skills`
- add `.gemini/commands -> commands` only for Gemini-native command assets

### 2. Add generated Gemini assets

During Gemini sync / brief generation:

- create or migrate `settings.json`
- preserve `config.json` if present
- generate `.gemini/commands/completeness-check.toml`
- generate `.gemini/commands/git-workflow.toml`
- merge `mcpServers` from `.mcp.json` into `settings.json`

### 3. Update `.ai/scripts/harness-doctor.sh`

The doctor script must stop treating `tools` as the only valid Gemini path.

It should:

- require canonical Gemini assets:
  - `settings.json`
  - `skills`
  - `GEMINI.md`
- allow `tools` as a bridge artifact
- report `.mcp.json` presence and whether Gemini settings reflect it

### 4. Update the Gemini brief output

The Gemini brief should:

- reference `.gemini/skills/...`
- include a Gemini commands section
- stop implying that only “tools” exist

### 5. Update tests

Revise Gemini assertions across the current test suite for:

- `settings.json`
- `skills`
- compatibility `tools`
- generated command files
- Gemini brief command section

## Verification Checklist

```text
┌──────────────────────────────────────┬────────────────────────────────────────────┐
│ Check                                │ Expected Result                            │
├──────────────────────────────────────┼────────────────────────────────────────────┤
│ GEMINI.md                            │ points to gemini brief                     │
│ .gemini/settings.json                │ exists and is canonical                    │
│ .gemini/skills                       │ exists and points to shared skills         │
│ .gemini/tools                        │ still exists as compatibility symlink      │
│ .gemini/commands                     │ exists with generated .toml commands       │
│ .mcp.json -> settings.json           │ mcpServers projected                       │
│ Gemini brief                         │ references .gemini/skills and /commands    │
│ harness-doctor.sh                    │ passes on bridge layout                    │
│ Gemini tests                         │ reflect canonical + compatibility layout   │
└──────────────────────────────────────┴────────────────────────────────────────────┘
```

## Issue Matrix

| ID | Area | Gap | Severity | Required Fix |
|---|---|---|---|---|
| G-01 | Structure | Active adapter still uses `tools` as canonical | Critical | Add `skills` as canonical, keep `tools` as bridge |
| G-02 | Config | Active adapter still uses `config.json` | Major | Move canonical config to `settings.json` |
| G-03 | Commands | Gemini commands exist only as markdown descriptions | Major | Generate `.gemini/commands/*.toml` |
| G-04 | MCP | `.mcp.json` is disconnected from Gemini settings | Major | Project `mcpServers` into `settings.json` |
| G-05 | Validation | Doctor script hardcodes `tools` | Major | Update health checks to bridge model |
| G-06 | Retrofit | Retrofit and active adapter disagree | Major | Align creation, validation, and retrofit contracts |
| G-07 | Tests | Gemini tests encode legacy layout | Major | Update test expectations to canonical-plus-bridge |

## Study Conclusion

The Gemini problem in this repository is not just one wrong path. It is a
three-layer mismatch:

1. generation logic creates the legacy shape
2. health checks validate the legacy shape
3. retrofit logic already points toward the standard shape

That is why Gemini alignment must be handled as a coordinated bridge, not as a
single-file rename.

## Related Drafts

This formal study supersedes the current Gemini drafts:

- `docs/gemini-study-pack.md`
- `docs/gemini-alignment-implementation.md`
- `docs/gemini-gaps-analysis.md`
