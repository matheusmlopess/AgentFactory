# Harness Identity Block
<!-- version: 1.1.0 -->

Issue: #115 · Cross-adapter navigation header compiled into every brief

Every adapter brief (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`) carries a standard
`## Harness` block that identifies the project, maps all adapter briefs, and
tells any agent exactly how to navigate the `.ai/` harness — regardless of which
CLI picked up the project.

---

## 1. Overview

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  THE PROBLEM THIS SOLVES                                               │
  │                                                                        │
  │  Project started with Claude. Developer switches to Codex.            │
  │  Codex reads AGENTS.md — no mention of .ai/, no mention of skills,   │
  │  no mention that CLAUDE.md has a full compiled brief next door.       │
  │                                                                        │
  │  The agent is flying blind. It reinvents context it doesn't need to. │
  └──────────────────────────────────────────────────────────────────────┘
```

The Harness Identity Block is a structural invariant: injected into **every**
compiled brief, for **every** adapter, unconditionally. It cannot be disabled
by removing a section key. It answers three questions immediately:

1. What project is this? (AgentFactory harness)
2. Where is the canonical context? (`.ai/`)
3. Where are all the other adapter briefs? (cross-adapter table)

---

## 2. Architecture

### 2.1 Where it lives in the compiler

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  src/agent_gen/librarian.py                                           │
  └──────────────────────────────────────────────────────────────────────┘

  _fmt_harness_identity(adapter_name: str) → str
      ↑
      called unconditionally in _render_brief()
      NOT part of section_order (cannot be removed by config)

  _render_brief(adapter_name, config, data):
      sections = []
      sections.append(header)                      ← @compiled-by metadata
      sections.append(_fmt_harness_identity(...))  ← harness block (unconditional)
      if data["project_context"]:                  ← NEW (#125)
          sections.append("## Project Context\n\n" + fitted_preamble)
      for section_key in config["section_order"]:  ← skills/commands/rules
          ...
      return "\n\n".join(sections)
```

### 2.2 Compilation pipeline

```
  agentfactory-gen brief   (or adapter-add, or init)
       │
       ▼
  Librarian._compile_adapter_briefs()
       │
       └─ for each activated adapter:
               _render_brief(adapter_name, config, data)
                    │
                    ├─ header block   (<!-- @compiled-by ... -->)
                    ├─ ## Harness    ← _fmt_harness_identity()
                    ├─ ## Project Context  ← NEW (#125, budget-fitted preamble)
                    ├─ ## Available Skills
                    ├─ ## Commands   (claude only)
                    ├─ ## Registered Agents
                    └─ ## Behavior Rules
                    │
                    ▼
              .ai/adapters/<name>/brief.md  (written to disk)
              CLAUDE.md / AGENTS.md / GEMINI.md  (root symlinks)

       Also: _compile_agentfactory_md()  ← NEW (#125)
              → upserts @commands + @rules into .ai/AgentFactory.md
```

---

## 3. Block Content

### 3.1 What the block looks like (claude adapter)

```
  ## Harness

  AgentFactory project. All adapters share the same harness context.

  ┌──────────────────────────────────────────┐
  │  Harness root : .ai/                     │
  │  This adapter : claude                   │
  │  Recompile    : agentfactory-gen brief   │
  └──────────────────────────────────────────┘

  Shared context (read these to understand the project):

    .ai/AgentFactory.md         ← project overview + master compiled brief
    .ai/skills/               ← skill specs (symlinked per adapter)
    .ai/rules/                ← behavior rules compiled into this brief
    .ai/agent-manifest.json   ← global agent registry
    .ai/memory/milestones.md  ← issue and milestone tracking

  All adapter briefs (same project, different CLI):

    claude   CLAUDE.md            → .ai/adapters/claude/brief.md ← YOU ARE HERE
    codex    AGENTS.md / CODEX.md → .ai/adapters/codex/brief.md
    gemini   GEMINI.md            → .ai/adapters/gemini/brief.md

  If switching CLI: run `agentfactory-gen brief`
```

### 3.2 YOU ARE HERE marker

The `← YOU ARE HERE` suffix appears on exactly one row — the row matching
`adapter_name`. All other adapters are listed without it. This makes the block
scannable in under a second: the agent doesn't need to read all rows.

### 3.3 Cross-adapter table is always complete

The table is generated from `_FORMAT_REGISTRY` — the full known adapter set —
regardless of which adapters are currently activated. A project that has only
ever activated Claude still shows Codex and Gemini rows. This is intentional:
the value of the cross-reference is highest at the moment of first swap, before
the new adapter has been activated.

---

## 4. How the Swap Works

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  ADAPTER SWAP — STEP BY STEP                                          │
  └──────────────────────────────────────────────────────────────────────┘

  Scenario: project started on Claude, switching to Codex

  1. Developer opens project in Codex CLI
        Codex reads AGENTS.md (its root brief)
        │
        └─ ## Harness block at the top:
               "This adapter : codex"
               "claude → .ai/adapters/claude/brief.md"
               "codex  → .ai/adapters/codex/brief.md ← YOU ARE HERE"
               "gemini → .ai/adapters/gemini/brief.md"
        Codex now knows:
          · the harness lives at .ai/
          · skills are at .ai/skills/
          · Claude's full brief is at .ai/adapters/claude/brief.md
          · agentfactory-gen brief resyncs everything

  2. If .ai/adapters/codex/ does not exist yet:
        agentfactory-gen adapter add codex
        → activates adapter, compiles codex brief with identity block

  3. If briefs are stale after pulling new code:
        agentfactory-gen brief
        → recompiles all active adapter briefs
        → identity block regenerated with current adapter list
```

---

## 5. Adding a New Adapter

When a new adapter is registered in `_FORMAT_REGISTRY`, it automatically
appears in the identity block of **all existing** briefs on the next
`agentfactory-gen brief` run — no manual update required.

```python
# src/agent_gen/librarian.py

_FORMAT_REGISTRY = {
    "claude":  { ... },
    "codex":   { ... },
    "gemini":  { ... },
    "new-cli": { ... },   # ← added here → appears in all briefs automatically
}
```

---

## 6. Integration Points

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  INTEGRATION MAP                                                       │
  └──────────────────────────────────────────────────────────────────────┘

  Calls _fmt_harness_identity():
    Librarian._render_brief()   ← every compilation path

  Triggers _render_brief():
    agentfactory-gen brief      ← manual recompile
    agentfactory-gen adapter add <name>  ← on adapter activation
    agentfactory-gen init       ← on project init (via _compile_adapter_briefs)
    agentfactory-gen import     ← on agent import (updates harness)

  Output locations:
    .ai/adapters/claude/brief.md   → symlinked as CLAUDE.md
    .ai/adapters/codex/brief.md    → symlinked as AGENTS.md + CODEX.md
    .ai/adapters/gemini/brief.md   → symlinked as GEMINI.md
```

---

## 7. Troubleshooting

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  Symptom                        │  Fix                                │
  ├─────────────────────────────────┼─────────────────────────────────────┤
  │  ## Harness missing from brief  │  Brief was compiled before this     │
  │                                 │  feature. Run:                      │
  │                                 │  agentfactory-gen brief             │
  ├─────────────────────────────────┼─────────────────────────────────────┤
  │  New adapter not in the table   │  Adapter not yet in _FORMAT_REGISTRY│
  │                                 │  in librarian.py. Add entry, then   │
  │                                 │  agentfactory-gen brief             │
  ├─────────────────────────────────┼─────────────────────────────────────┤
  │  YOU ARE HERE on wrong row      │  Brief was compiled for a different  │
  │                                 │  adapter. Run adapter-add for the   │
  │                                 │  correct one, or check symlinks     │
  ├─────────────────────────────────┼─────────────────────────────────────┤
  │  Codex reads AGENTS.md but      │  .ai/adapters/codex/ not yet        │
  │  skills/ symlink missing        │  activated. Run:                    │
  │                                 │  agentfactory-gen adapter add codex │
  └─────────────────────────────────┴─────────────────────────────────────┘
```
