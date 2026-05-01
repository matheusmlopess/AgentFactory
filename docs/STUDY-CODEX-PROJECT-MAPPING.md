# Study: Codex Project Mapping
<!-- version: 1.0.0 -->

This study maps how Codex project context is discovered in practice, how AgentFactory
currently models that surface, and where the harness still has blind spots.

## Purpose

Use this document when:
- documenting Codex support in AgentFactory
- deciding what AgentFactory should own versus merely observe
- breaking mapping gaps into targeted GitHub issues

The study is based on:
- current repository layout
- `src/agent_gen/cli.py`
- `src/agent_gen/librarian.py`
- current automated tests
- installed local Codex home layout observed on this machine

It intentionally separates:
- **native Codex surfaces**: paths and conventions Codex itself uses
- **AgentFactory-managed surfaces**: paths the harness creates or wires
- **AgentFactory-observed external surfaces**: relevant paths AgentFactory may inspect but should not rewrite by default
- **plugin-provided surfaces**: capabilities introduced by Codex plugins

## Classification Map

```text
┌────────────────────────────── Codex Surface Classes ──────────────────────────────┐
│ Native Codex                                                                       │
│  ├─ AGENTS.md                                                                      │
│  ├─ CODEX.md                                                                       │
│  ├─ .codex/                                                                        │
│  └─ .mcp.json                                                                      │
│                                                                                   │
│ AgentFactory-managed                                                               │
│  ├─ .ai/adapters/codex/brief.md                                                    │
│  ├─ .ai/adapters/codex/config.toml                                                 │
│  ├─ .ai/adapters/codex/skills    -> ../../skills                                   │
│  ├─ .ai/adapters/codex/prompts   -> ../../commands                                 │
│  ├─ .codex                  -> .ai/adapters/codex                                  │
│  ├─ AGENTS.md               -> .ai/adapters/codex/brief.md                         │
│  └─ CODEX.md                -> .ai/adapters/codex/brief.md                         │
│                                                                                   │
│ AgentFactory-observed external                                                     │
│  ├─ project-root .mcp.json                                                         │
│  ├─ ~/.codex/config.toml                                                           │
│  ├─ ~/.codex/skills/                                                                │
│  ├─ ~/.codex/rules/                                                                 │
│  └─ ~/.codex/memories/                                                              │
│                                                                                   │
│ Plugin-provided                                                                     │
│  ├─ ~/.codex/plugins/cache/...                                                     │
│  ├─ plugin skill bundles                                                           │
│  └─ plugin MCP / app / tool capabilities                                           │
└───────────────────────────────────────────────────────────────────────────────────┘
```

## Observed Project Layout

This repo currently exposes Codex through AgentFactory like this:

```text
AgentFactory.old/
├─ AGENTS.md  -> .ai/adapters/codex/brief.md
├─ CODEX.md   -> .ai/adapters/codex/brief.md
├─ .codex     -> .ai/adapters/codex
├─ .mcp.json
└─ .ai/
   ├─ AgentFactory.md
   ├─ agent-manifest.json
   ├─ commands/
   ├─ skills/
   ├─ rules/
   ├─ memory/
   └─ adapters/
      └─ codex/
         ├─ brief.md
         ├─ config.toml
         ├─ prompts -> ../../commands
         └─ skills  -> ../../skills
```

Observed global Codex home on this machine:

```text
~/.codex/
├─ config.toml
├─ skills/
│  └─ .system/
├─ plugins/
│  └─ cache/
├─ rules/
├─ memories/
├─ sessions/
├─ log/
└─ cache/
```

## Source-of-Truth Matrix

```text
┌───────────────────────┬──────────────────────────────────────┬──────────────────────┬─────────────────────┬──────────┐
│ Capability            │ Path / Surface                       │ Primary Owner        │ Auto-used by Codex  │ AF State │
├───────────────────────┼──────────────────────────────────────┼──────────────────────┼─────────────────────┼──────────┤
│ Root instructions     │ AGENTS.md                            │ Native + AF wiring   │ Yes                 │ Managed  │
│ Root instructions     │ CODEX.md                             │ Native + AF wiring   │ Yes                 │ Managed  │
│ Project adapter dir   │ .codex/                              │ Native + AF wiring   │ Yes                 │ Managed  │
│ Compiled brief        │ .ai/adapters/codex/brief.md          │ AgentFactory         │ Indirect            │ Managed  │
│ Adapter config        │ .ai/adapters/codex/config.toml       │ AgentFactory         │ Via .codex symlink  │ Managed  │
│ Skill exposure        │ .ai/adapters/codex/skills            │ AgentFactory         │ Via .codex symlink  │ Managed  │
│ Prompt exposure       │ .ai/adapters/codex/prompts           │ AgentFactory         │ Via .codex symlink  │ Managed  │
│ Project MCP config    │ .mcp.json                            │ Native project       │ Yes                 │ Observed │
│ Shared skills source  │ .ai/skills/                          │ AgentFactory         │ Indirect            │ Managed  │
│ Shared prompts source │ .ai/commands/                        │ AgentFactory         │ Indirect            │ Managed  │
│ Shared rules          │ .ai/rules/                           │ AgentFactory         │ Through brief only  │ Managed  │
│ Global config         │ ~/.codex/config.toml                 │ User environment     │ Yes                 │ External │
│ Global skills         │ ~/.codex/skills/                     │ User environment     │ Yes                 │ External │
│ Global rules          │ ~/.codex/rules/                      │ User environment     │ Yes                 │ External │
│ Plugins               │ ~/.codex/plugins/cache/...           │ Plugin system        │ Yes                 │ External │
│ Plugin tools / MCP    │ runtime tool/plugin registration     │ Plugin system        │ Yes                 │ External │
│ Memories / sessions   │ ~/.codex/memories, ~/.codex/sessions │ User environment     │ Yes                 │ External │
└───────────────────────┴──────────────────────────────────────┴──────────────────────┴─────────────────────┴──────────┘
```

`AF State` values:
- `Managed`: AgentFactory creates, wires, or documents it as part of the harness
- `Observed`: relevant local surface, but not currently modeled in code/docs as a first-class contract
- `External`: outside project ownership; should generally be inventoried, not rewritten

## What AgentFactory Currently Implements

### In `init`

`init_project()` currently:
- creates `.ai/adapters/codex/`
- writes `.ai/adapters/codex/config.toml`
- calls `_ensure_adapter_wiring()` so Codex gets:
  - `skills -> ../../skills`
  - `prompts -> ../../commands`
- compiles `.ai/adapters/codex/brief.md`
- creates root symlinks:
  - `AGENTS.md -> .ai/adapters/codex/brief.md`
  - `CODEX.md -> .ai/adapters/codex/brief.md`
- creates `.codex -> .ai/adapters/codex`

### In the format registry

Current Codex adapter contract in `_FORMAT_REGISTRY["codex"]`:
- root files: `AGENTS.md`, `CODEX.md`
- folder symlink: `.codex`
- wiring:
  - `skills -> ../../skills`
  - `prompts -> ../../commands`
- config file: `config.toml`
- default config:
  - `model = "gpt-5.4"`

### In retrofit/import mapping

Current Codex conversion profile in `CONVERSION_PROFILES["codex"]` maps:
- `.codex/prompts` -> `skills/prompts`
- `codex.md` -> `docs/codex.md`
- `.codex/templates` -> `docs/templates`
- `.codex/workflows` -> `orchestration/workflows`
- `AGENTS.md` -> `orchestration/AGENTS.md`

This is narrower than the active adapter contract and has a naming inconsistency:
- active root-file contract uses `CODEX.md`
- retrofit profile uses `codex.md`

### In diagnostics

`harness-doctor.sh` currently checks:
- `.ai/adapters/codex/prompts`

It does not currently check:
- `.ai/adapters/codex/skills`
- `.ai/adapters/codex/config.toml`
- root `AGENTS.md`
- root `CODEX.md`
- project `.mcp.json`
- global `~/.codex/*`
- plugin surfaces

## Current Status by Surface

```text
┌────────────────────────────────────┬──────────────┬─────────────────────────────────────────────────────┐
│ Surface                            │ Status       │ Notes                                               │
├────────────────────────────────────┼──────────────┼─────────────────────────────────────────────────────┤
│ AGENTS.md / CODEX.md               │ Works        │ Created by init; covered by tests.                  │
│ .codex symlink                     │ Works        │ Created by init; points to .ai/adapters/codex.      │
│ codex brief compilation            │ Works        │ Covered by CLI swap and integration tests.          │
│ codex skills wiring                │ Works        │ Explicit tests for symlink presence.                │
│ codex prompts wiring               │ Works        │ Explicit tests for symlink target.                  │
│ codex config creation              │ Works        │ `config.toml` scaffolded and preserved on rerun.    │
│ project .mcp.json awareness        │ Partial      │ Exists in repos; not part of AF mapping contract.   │
│ global ~/.codex config awareness   │ Partial      │ Discoverable manually; not modeled by AF.           │
│ global ~/.codex skills/rules       │ Partial      │ Visible externally; not surfaced by harness.        │
│ plugin inventory awareness         │ Partial      │ Visible externally; not surfaced by harness.        │
│ plugin MCP/app/tool mapping        │ Missing      │ No explicit AF contract or diagnostics.             │
│ retrofit CODEX.md naming parity    │ Missing      │ `codex.md` vs `CODEX.md` mismatch remains.          │
│ doctor coverage for codex surface  │ Partial      │ Checks prompts only; misses several codex assets.   │
└────────────────────────────────────┴──────────────┴─────────────────────────────────────────────────────┘
```

## What Is Native Versus AgentFactory-Specific

Important distinction:

- `AGENTS.md`, `CODEX.md`, `.codex`, `.mcp.json`, and `~/.codex/*` are part of Codex-facing runtime behavior or configuration surface.
- `.ai/adapters/codex/*` is an AgentFactory harness implementation detail.
- `.ai/skills` and `.ai/commands` are AgentFactory shared sources, not native Codex project conventions.
- `.ai/agents/*/scripts`, `.ai/agents/*/orchestration`, and the 5-directory standard are AgentFactory concepts. Codex does not auto-discover those by folder name alone.

That means AgentFactory should avoid claiming:
- that `scripts/` is a native Codex discovery folder
- that `agents/` is a native Codex project registry
- that plugin tools are represented by any single project path

## Historical Note

`docs/TEST-REPORT-HARNESS-INIT.md` records an older real-world run where `init`
did not create non-primary root links. Current code and tests show that this gap
has since been fixed. Treat that report as historical evidence, not current truth,
for these items:
- `AGENTS.md`
- `CODEX.md`
- `GEMINI.md`

The same report is still useful for:
- chronology of `init`
- real-world repo initialization context
- identifying how regressions looked when they existed

## Required AgentFactory Contract Going Forward

AgentFactory should define Codex support in four buckets.

### 1. Must manage

- `.ai/adapters/codex/brief.md`
- `.ai/adapters/codex/config.toml`
- `.ai/adapters/codex/skills`
- `.ai/adapters/codex/prompts`
- root `AGENTS.md`
- root `CODEX.md`
- root `.codex`

### 2. Must observe locally

- root `.mcp.json`

Minimum expectation:
- detect presence
- document that it contributes Codex runtime capabilities
- report if the file exists but AgentFactory has no visibility into declared MCP servers

### 3. May inventory externally, but should not rewrite by default

- `~/.codex/config.toml`
- `~/.codex/skills/`
- `~/.codex/rules/`
- `~/.codex/plugins/`
- `~/.codex/memories/`

### 4. Must document as plugin-provided

- plugin skills
- plugin MCP/app/tool surfaces
- cached plugin bundles under `~/.codex/plugins/cache/...`

## Open Gaps

The main unresolved gaps are:

1. `CONVERSION_PROFILES["codex"]` does not match the active root-file contract.
2. Codex mapping docs do not currently describe `.mcp.json` as a first-class observed surface.
3. Diagnostics do not validate most Codex-managed assets.
4. Global `~/.codex` and plugin surfaces are visible in practice but absent from AgentFactory’s formal mapping model.
5. Historical docs still imply some init gaps that current code has already fixed.

## Related Studies

- `docs/STUDY-CODEX-INIT-SCENARIOS.md`
- `docs/STUDY-CODEX-GAP-MATRIX.md`
- `docs/TEST-REPORT-HARNESS-INIT.md`
