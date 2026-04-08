# Implement Production-Grade Multi-CLI AI Harness (Claude + Codex + Gemini)

## Overview

This issue defines the full implementation of a **modular, production-grade AI harness** that supports:

- **Claude Code CLI** — Orchestrator layer (agents, memory, rules)
- **OpenAI Codex CLI** — Execution layer (fast iteration, shell-driven)
- **Gemini CLI** — Context discovery + skill layer (project ingestion, multi-tier skills)

The harness is **modular by design**: the shared layer is always present, but each CLI layer is **opt-in**. You can run a single-CLI setup (e.g., Claude-only), a dual setup (Claude + Gemini), or the full trio — without unused folders or files cluttering the project.

When multiple CLIs are active, the harness enables **seamless session handoff** between them via a shared session state protocol.

The harness uses a **tiered bootstrap protocol** to minimize context window consumption — loading only what's needed for each task rather than eagerly ingesting everything.

---

## Objectives

- Standardize AI-assisted development across one or more CLIs
- Provide a shared architectural context (single source of truth)
- Enable reusable skills, commands, and workflows
- Support agent-based orchestration (Claude + shared layer)
- Ensure consistency, reproducibility, and scalability
- **Allow opt-in per CLI — only install what you use**
- **Enable seamless CLI switching without updating core files** (when multi-CLI)
- **Maintain a tool-agnostic session state that any CLI can read/write**
- **Prevent decision re-litigation when switching between tools**
- **Keep bootstrap context under 5% of the CLI's context window for typical tasks**

---

## Modularity Model

The harness is composed of independent layers that can be installed individually.

```
┌─────────────────────────────────────────────────────┐
│                   SHARED LAYER                      │
│            (always required, always first)           │
│                                                     │
│  ARCHITECTURE · DOMAIN · CONSTRAINTS · STANDARDS    │
│  AGENTS · rules/ · skills/ (with MANIFEST)          │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │  CLAUDE  │ │  CODEX   │ │  GEMINI  │
    │ (opt-in) │ │ (opt-in) │ │ (opt-in) │
    └──────────┘ └──────────┘ └──────────┘
          │            │            │
          └────────────┼────────────┘
                       │
          ┌────────────┴────────────┐
          │     HANDOFF LAYER       │
          │  (auto-activates when   │
          │   2+ CLIs are present)  │
          └─────────────────────────┘
```

### Installation Profiles

| Profile | Layers Installed | Use Case |
|---------|-----------------|----------|
| `shared` | `ai/shared/` only | Foundation — add a CLI layer later |
| `claude` | `ai/shared/` + `ai/claude/` | Claude-only projects |
| `codex` | `ai/shared/` + `ai/codex/` | Codex-only projects |
| `gemini` | `ai/shared/` + `ai/gemini/` | Gemini-only projects |
| `claude+codex` | shared + claude + codex + adapters + handoff | Dual setup |
| `claude+gemini` | shared + claude + gemini + adapters + handoff | Dual setup |
| `full` | Everything | Full trio |

### Activation Rules

1. **Shared layer** → always present, always first
2. **Single CLI** → no adapters, no handoff layer, no `SESSION.md` / `session-state.json` (the CLI reads shared context directly via tiered bootstrap)
3. **2+ CLIs** → adapters + handoff layer auto-activate; `SESSION.md`, `session-state.json`, `DECISIONS.md`, and `CONFLICT_RESOLUTION.md` are created
4. **Adding a CLI later** → drop in its folder + adapter; handoff layer activates if now multi-CLI

### Manifest (`ai/harness.json`)

A lightweight manifest at `ai/harness.json` declares which CLIs are active, whether handoff is enabled, and token budgets for governance.

**Single-CLI example:**

```json
{
  "version": "1.0.0",
  "active_harnesses": ["claude"],
  "handoff_enabled": false,
  "shared": {
    "rules": ["api-design", "testing", "security", "performance", "refactoring"],
    "skills": ["security-review"]
  },
  "budgets": {
    "tier1_max_tokens": 5000,
    "core_doc_max_tokens": 1500,
    "rule_max_tokens": 750,
    "skill_max_tokens": 4000,
    "active_decisions_max": 30,
    "total_bootstrap_target": 15000,
    "total_bootstrap_ceiling": 25000
  }
}
```

**Multi-CLI example:**

```json
{
  "version": "1.0.0",
  "active_harnesses": ["claude", "gemini"],
  "handoff_enabled": true,
  "handoff": {
    "max_active_decisions": 30,
    "session_state_max_tokens": 1500
  },
  "shared": {
    "rules": ["api-design", "testing", "security", "performance", "refactoring"],
    "skills": ["security-review", "api-design", "db-migration"]
  },
  "budgets": {
    "tier1_max_tokens": 5000,
    "core_doc_max_tokens": 1500,
    "rule_max_tokens": 750,
    "skill_max_tokens": 4000,
    "active_decisions_max": 30,
    "total_bootstrap_target": 15000,
    "total_bootstrap_ceiling": 25000
  }
}
```

---

## Folder Structures by Profile

### Single CLI: Claude-Only

```
project-root/
├── ai/
│   ├── harness.json                         # Manifest: ["claude"], handoff: false
│   │
│   ├── shared/                              # ── SINGLE SOURCE OF TRUTH ──
│   │   ├── ARCHITECTURE.md                  # System design, component map, data flow
│   │   ├── DOMAIN.md                        # Business logic, ubiquitous language
│   │   ├── CONSTRAINTS.md                   # Hard boundaries, forbidden actions
│   │   ├── STANDARDS.md                     # Coding conventions, naming, patterns
│   │   ├── AGENTS.md                        # Agent roles, responsibilities
│   │   │
│   │   ├── skills/                          # ── SHARED SKILLS ──
│   │   │   ├── MANIFEST.md                  # Skill index — trigger keywords + paths
│   │   │   └── security-review/
│   │   │       ├── SKILL.md
│   │   │       ├── checklist.md
│   │   │       ├── reference.md
│   │   │       └── examples.md
│   │   │
│   │   └── rules/                           # ── SHARED RULES ──
│   │       ├── api-design.md
│   │       ├── testing.md
│   │       ├── security.md
│   │       ├── performance.md
│   │       └── refactoring.md
│   │
│   └── claude/                              # ── CLAUDE-SPECIFIC ──
│       ├── CLAUDE.md                        # Main instruction file (tiered refs)
│       └── .claude/
│           ├── settings.json
│           ├── settings.local.json
│           ├── tools/
│           ├── rules/                       # Claude-only overrides (with justification)
│           ├── skills/                      # Claude-only skills (rare)
│           ├── commands/
│           │   └── fix-issue.md
│           ├── agents/
│           │   └── code-reviewer.md
│           └── agent-memory/
│               └── code-reviewer/
│                   ├── MEMORY.md
│                   ├── state.json
│                   └── history.md
│
├── .mcp.json
└── src/
```

**What's NOT present**: no `ai/adapters/`, no `ai/codex/`, no `ai/gemini/`, no `SESSION.md`, no `session-state.json`, no `DECISIONS.md`, no `CONFLICT_RESOLUTION.md`.

### Single CLI: Codex-Only

```
project-root/
├── ai/
│   ├── harness.json                         # Manifest: ["codex"], handoff: false
│   │
│   ├── shared/
│   │   ├── ARCHITECTURE.md
│   │   ├── DOMAIN.md
│   │   ├── CONSTRAINTS.md
│   │   ├── STANDARDS.md
│   │   ├── AGENTS.md
│   │   ├── skills/
│   │   │   ├── MANIFEST.md
│   │   │   └── ...
│   │   └── rules/
│   │
│   └── codex/                               # ── CODEX-SPECIFIC ──
│       ├── codex.md                         # Main instruction file (tiered refs)
│       └── .codex/
│           ├── config.json
│           ├── prompts/
│           ├── workflows/
│           ├── history/
│           └── cache/
│
├── .mcp.json
└── src/
```

### Single CLI: Gemini-Only

```
project-root/
├── ai/
│   ├── harness.json                         # Manifest: ["gemini"], handoff: false
│   │
│   ├── shared/
│   │   ├── ARCHITECTURE.md
│   │   ├── DOMAIN.md
│   │   ├── CONSTRAINTS.md
│   │   ├── STANDARDS.md
│   │   ├── AGENTS.md
│   │   ├── skills/
│   │   │   ├── MANIFEST.md
│   │   │   └── ...
│   │   └── rules/
│   │
│   └── gemini/                              # ── GEMINI-SPECIFIC ──
│       ├── GEMINI.md                        # Main instruction file (tiered refs)
│       └── .gemini/
│           ├── config.json
│           ├── skills/
│           ├── extensions/
│           └── cache/
│
├── .mcp.json
└── src/
```

### Multi-CLI: Full Trio

```
project-root/
├── ai/
│   ├── harness.json                         # ["claude","codex","gemini"], handoff: true
│   │
│   ├── shared/                              # ── SINGLE SOURCE OF TRUTH ──
│   │   ├── ARCHITECTURE.md
│   │   ├── DOMAIN.md
│   │   ├── CONSTRAINTS.md
│   │   ├── STANDARDS.md
│   │   ├── AGENTS.md
│   │   ├── DECISIONS.md                     # ← only when multi-CLI (active, max 30)
│   │   ├── DECISIONS_ARCHIVE.md             # ← rotated decisions (not loaded on boot)
│   │   ├── DECISIONS_INDEX.md               # ← one-line summaries of all decisions
│   │   ├── SESSION.md                       # ← only when multi-CLI
│   │   ├── session-state.json               # ← only when multi-CLI
│   │   ├── CONFLICT_RESOLUTION.md           # ← only when multi-CLI (human ref, NOT loaded on boot)
│   │   │
│   │   ├── skills/
│   │   │   ├── MANIFEST.md                  # Skill index — loaded on boot, skills loaded on demand
│   │   │   └── security-review/
│   │   │       ├── SKILL.md
│   │   │       ├── checklist.md
│   │   │       ├── reference.md
│   │   │       └── examples.md
│   │   │
│   │   └── rules/
│   │       ├── api-design.md
│   │       ├── testing.md
│   │       ├── security.md
│   │       ├── performance.md
│   │       └── refactoring.md
│   │
│   ├── adapters/                            # ← only when multi-CLI
│   │   ├── claude-bootstrap.md
│   │   ├── codex-bootstrap.md
│   │   └── gemini-bootstrap.md
│   │
│   ├── claude/
│   │   ├── CLAUDE.md
│   │   └── .claude/
│   │       ├── settings.json
│   │       ├── settings.local.json
│   │       ├── tools/
│   │       ├── rules/
│   │       ├── skills/
│   │       ├── commands/
│   │       │   └── fix-issue.md
│   │       ├── agents/
│   │       │   └── code-reviewer.md
│   │       └── agent-memory/
│   │           └── code-reviewer/
│   │               ├── MEMORY.md
│   │               ├── state.json
│   │               └── history.md
│   │
│   ├── codex/
│   │   ├── codex.md
│   │   └── .codex/
│   │       ├── config.json
│   │       ├── prompts/
│   │       ├── workflows/
│   │       ├── history/
│   │       └── cache/
│   │
│   └── gemini/
│       ├── GEMINI.md
│       └── .gemini/
│           ├── config.json
│           ├── skills/
│           ├── extensions/
│           └── cache/
│
├── .mcp.json
├── .gitignore
├── .worktreeinclude
├── README.md
└── src/
```

---

## Tiered Bootstrap Protocol

> The single most important efficiency mechanism in the harness. Replaces the naive "load everything" approach with context-aware, progressive loading.

### Why This Matters

Loading everything eagerly on every session start is the dominant cost driver. A mature full-trio project with 10 skills and 100 decisions would consume ~57,000 tokens (28.5% of Claude's 200K context) before any actual work begins. The tiered protocol cuts this to ~7,500–8,500 tokens (3.75–4.25%) for typical tasks.

### Tier Definitions

```
┌──────────────────────────────────────────────────────────────────┐
│ TIER 1 — ALWAYS LOADED                        ~3,000–5,000 tok  │
│ Hard constraints, coding standards, session state, skill index   │
│                                                                  │
│ Loaded unconditionally on every session start.                   │
│ These files are small by design and always relevant.             │
├──────────────────────────────────────────────────────────────────┤
│ TIER 2 — TASK-MATCHED                         ~2,000–5,000 tok  │
│ Relevant rules, relevant skills, active decisions                │
│                                                                  │
│ Loaded after reading the user's request. The CLI matches the     │
│ task against MANIFEST.md triggers and rule scopes to decide      │
│ which files to pull.                                             │
├──────────────────────────────────────────────────────────────────┤
│ TIER 3 — ON DEMAND                            ~1,000–5,000 tok  │
│ Architecture, domain, agents, skill reference.md, decision       │
│ archive                                                          │
│                                                                  │
│ Loaded only when the task explicitly requires it (system design, │
│ domain modeling, deep skill reference, historical decisions).     │
└──────────────────────────────────────────────────────────────────┘
```

### Tier 1 — Always Loaded

| File | Est. Tokens | Rationale |
|------|------------|-----------|
| `harness.json` | ~75 | Topology awareness |
| CLI instruction file (CLAUDE.md / codex.md / GEMINI.md) | ~500 | Core identity + directives |
| `CONSTRAINTS.md` | ~500 | Hard boundaries — always relevant |
| `STANDARDS.md` | ~750 | Coding conventions — always relevant |
| `skills/MANIFEST.md` | ~300 | Skill index for lazy loading |
| `session-state.json` (multi-CLI) | ~500 | Handoff context |
| `SESSION.md` (multi-CLI) | ~500 | Handoff context |
| **Tier 1 Total** | **~2,625–3,125** | |

### Tier 2 — Task-Matched

| File | Est. Tokens | Trigger |
|------|------------|---------|
| Matching rules (1–2 files) | ~500–1,500 | Task mentions API, testing, security, etc. |
| Matching skill (SKILL.md + checklist.md) | ~500–1,250 | MANIFEST trigger keywords match task |
| `DECISIONS.md` (active, ≤30 entries) | ~1,500–4,500 | Always loaded in multi-CLI; skipped in single-CLI |
| **Tier 2 Total** | **~2,500–7,250** | |

### Tier 3 — On Demand

| File | Est. Tokens | Trigger |
|------|------------|---------|
| `ARCHITECTURE.md` | ~1,000 | Task involves system design, component changes |
| `DOMAIN.md` | ~750 | Task involves business logic, domain modeling |
| `AGENTS.md` | ~500 | Task involves multi-agent orchestration |
| Skill `reference.md` | ~500–2,000 | Deep domain knowledge needed |
| Skill `examples.md` | ~250–1,000 | Example patterns needed |
| `DECISIONS_ARCHIVE.md` | variable | Historical lookup for conflicts |
| **Tier 3 Total** | **~1,000–5,250** | Only what's needed |

### Token Cost by Scenario (Optimized)

| Scenario | Tiers Loaded | Tokens | % of 200K | Cost/Init |
|----------|-------------|--------|-----------|-----------|
| Single CLI, fresh, simple task | T1 | ~3,000 | 1.5% | $0.009 |
| Single CLI, mature, typical task | T1 + T2 (1 rule, 1 skill) | ~5,500 | 2.75% | $0.017 |
| Single CLI, complex task (design work) | T1 + T2 + T3 | ~10,000 | 5.0% | $0.030 |
| Multi-CLI, fresh, simple task | T1 + T2 (decisions) | ~5,000 | 2.5% | $0.015 |
| Multi-CLI, mature, typical task | T1 + T2 (2 rules, 1 skill, 20 dec) | ~8,000 | 4.0% | $0.024 |
| Multi-CLI, worst case (design + deep skill) | T1 + T2 + T3 | ~15,000 | 7.5% | $0.045 |

Compare to the **unoptimized** approach:

| Scenario | Unoptimized Tokens | Optimized Tokens | Reduction |
|----------|-------------------|-----------------|-----------|
| Single CLI, 5 skills | ~22,800 | ~5,500 | **76%** |
| Multi-CLI, 5 skills, 20 decisions | ~27,000 | ~8,000 | **70%** |
| Multi-CLI, 10 skills, 100 decisions | ~57,000 | ~15,000 | **74%** |

---

## System Design Principles

### 1. Shared Context First (Single Source of Truth)

All active CLIs must align to the shared layer. No tool may define conflicting rules.

| File | Purpose | Update Frequency | Present When | Bootstrap Tier |
|------|---------|-----------------|--------------|---------------|
| `ARCHITECTURE.md` | System design, component map | Low (milestones) | Always | Tier 3 |
| `DOMAIN.md` | Business logic, ubiquitous language | Low | Always | Tier 3 |
| `CONSTRAINTS.md` | Hard boundaries, forbidden actions | Low | Always | **Tier 1** |
| `STANDARDS.md` | Coding conventions, naming, patterns | Low | Always | **Tier 1** |
| `AGENTS.md` | Agent roles, interaction model | Low | Always | Tier 3 |
| `DECISIONS.md` | Append-only decision log (active) | Every session | Multi-CLI only | Tier 2 |
| `DECISIONS_ARCHIVE.md` | Rotated old decisions | On rotation | Multi-CLI only | Tier 3 |
| `DECISIONS_INDEX.md` | One-line summaries of all decisions | On rotation | Multi-CLI only | Tier 2 |
| `SESSION.md` | Human-readable handoff state | Every session | Multi-CLI only | **Tier 1** |
| `session-state.json` | Machine-readable handoff state | Every session | Multi-CLI only | **Tier 1** |
| `CONFLICT_RESOLUTION.md` | Precedence rules | Low | Multi-CLI only | **Not loaded** (human reference) |

---

### 2. Session Handoff Protocol (Multi-CLI Only)

> Only activates when `harness.json` has 2+ active harnesses.

#### `session-state.json` Schema

```json
{
  "$schema": "ai/shared/session-state.schema.json",
  "version": "1.0.0",
  "last_updated": "2025-06-15T14:32:00Z",
  "last_tool": "claude",
  "session_id": "uuid-v4",

  "context": {
    "branch": "feature/auth-module",
    "last_commit": "abc1234",
    "working_files": ["src/auth/handler.ts", "src/auth/middleware.ts"],
    "dirty_files": ["src/auth/handler.ts"]
  },

  "progress": {
    "current_task": "Implement JWT refresh token rotation",
    "completed": [
      "Basic JWT signing",
      "Login endpoint",
      "Token validation middleware"
    ],
    "blocked": [],
    "next_steps": [
      "Add refresh token endpoint",
      "Add token revocation",
      "Write integration tests"
    ]
  },

  "decisions_since_last_handoff": [
    {
      "id": "DEC-012",
      "summary": "Use rotating refresh tokens instead of sliding expiry",
      "rationale": "Better security posture for mobile clients"
    }
  ],

  "open_questions": [
    "Should revoked tokens be stored in Redis or DB?"
  ],

  "agent_states": {
    "code-reviewer": {
      "last_review": "src/auth/handler.ts",
      "pending_findings": 2
    }
  }
}
```

#### `SESSION.md` Format

```markdown
# Session Handoff — 2025-06-15

## Last Tool: Claude
## Branch: feature/auth-module
## Session ID: <uuid>

## What Was Done
- Implemented JWT signing with RS256
- Created login endpoint with rate limiting
- Added token validation middleware

## Key Decisions
- DEC-012: Rotating refresh tokens (not sliding expiry) — better for mobile

## Current State
- `src/auth/handler.ts` has uncommitted changes (refresh endpoint WIP)
- Middleware is complete and tested

## Open Questions
- Redis vs DB for revoked token storage?

## Next Steps
1. Finish refresh token endpoint
2. Add token revocation
3. Integration tests for full auth flow
```

#### Handoff Flow

```
┌─────────────────────────────────────────────────────────┐
│                    SESSION START                         │
│                                                         │
│  CLI reads harness.json → checks if handoff enabled     │
│    ├─► Single CLI: Tier 1 shared context directly        │
│    └─► Multi CLI: Tier 1 via bootstrap adapter           │
│          └─► Read session-state.json + SESSION.md        │
│               └─► CLI has full context from prev session │
│                                                         │
│  CLI reads user's task → loads Tier 2 (matching rules,  │
│  skills, decisions)                                     │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    DURING WORK                          │
│                                                         │
│  CLI loads Tier 3 on demand as task evolves             │
│  CLI appends to DECISIONS.md (if multi-CLI)             │
│  CLI updates SESSION.md as running log (if multi-CLI)   │
│  Agent states update in agent-memory/ (Claude only)     │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    SESSION END                           │
│                                                         │
│  If multi-CLI:                                          │
│    CLI writes final snapshot to session-state.json      │
│    CLI finalizes SESSION.md                             │
│    If DECISIONS.md > max_active_decisions:              │
│      rotate oldest → DECISIONS_ARCHIVE.md               │
│      update DECISIONS_INDEX.md                          │
│    Commit session files (optional, recommended)         │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    SWITCH CLI                            │
│                                                         │
│  New CLI picks up from SESSION START                    │
│  Core files unchanged — only session state rotates      │
└─────────────────────────────────────────────────────────┘
```

---

### 3. Bootstrap Adapters (Multi-CLI Only)

Each CLI's main instruction file includes its bootstrap adapter as the **first directive** when handoff is enabled. In single-CLI mode, the instruction file encodes the tiered protocol directly — no adapter needed.

#### Single-CLI Mode: `CLAUDE.md` (tiered, direct)

```markdown
# Claude Instructions

## Tier 1 — Always Load
@ai/harness.json
@ai/shared/CONSTRAINTS.md
@ai/shared/STANDARDS.md
@ai/shared/skills/MANIFEST.md

## Tier 2 — Load After Reading Task
Load matching rules from ai/shared/rules/ based on task domain.
Load matching skills from ai/shared/skills/ based on MANIFEST triggers.

## Tier 3 — Load On Demand
@ai/shared/ARCHITECTURE.md → only if task involves system design
@ai/shared/DOMAIN.md → only if task involves business logic
@ai/shared/AGENTS.md → only if task involves orchestration
Skill reference.md → only if deep domain knowledge needed

## Claude-Specific Rules
...
```

#### Multi-CLI Mode: `CLAUDE.md` (via adapter)

```markdown
# Claude Instructions

## Bootstrap
@ai/adapters/claude-bootstrap.md

## Claude-Specific Rules
...
```

#### `claude-bootstrap.md` (Tiered)

```markdown
# Claude Bootstrap Protocol v2

## Tier 1 — Always (before reading user's task)
1. Read `ai/harness.json` — topology + budgets
2. Read `ai/shared/CONSTRAINTS.md` — hard boundaries
3. Read `ai/shared/STANDARDS.md` — coding conventions
4. Read `ai/shared/skills/MANIFEST.md` — skill index
5. Read `ai/shared/session-state.json` — restore context from previous session
6. Read `ai/shared/SESSION.md` — understand what was done and why

## Tier 2 — Task-Matched (after reading user's task)
7. Load rules from `ai/shared/rules/` that match the task domain
8. Load skills from `ai/shared/skills/` that match MANIFEST triggers
9. Read `ai/shared/DECISIONS.md` — active decisions only
10. Read `ai/shared/DECISIONS_INDEX.md` — scan for relevant archived decisions

## Tier 3 — On Demand (only if task requires)
11. `ARCHITECTURE.md` — if task involves system design or component changes
12. `DOMAIN.md` — if task involves business logic or domain modeling
13. `AGENTS.md` — if task involves orchestration or agent coordination
14. Skill `reference.md` — if deep domain knowledge is needed
15. `DECISIONS_ARCHIVE.md` — if an indexed decision needs full context

## On Session End
1. Update `ai/shared/session-state.json` with current state
2. Update `ai/shared/SESSION.md` with session summary
3. Append any new decisions to `ai/shared/DECISIONS.md`
4. If DECISIONS.md exceeds max_active_decisions: rotate oldest to archive
5. Persist agent memory to `ai/claude/.claude/agent-memory/`
```

#### `codex-bootstrap.md` (Tiered)

```markdown
# Codex Bootstrap Protocol v2

## Tier 1 — Always
1. Read `ai/harness.json`
2. Read `ai/shared/CONSTRAINTS.md`
3. Read `ai/shared/STANDARDS.md`
4. Read `ai/shared/skills/MANIFEST.md`
5. Read `ai/shared/session-state.json`
6. Read `ai/shared/SESSION.md`

## Tier 2 — Task-Matched
7. Load matching rules from `ai/shared/rules/`
8. Load matching skills from `ai/shared/skills/`
9. Read `ai/shared/DECISIONS.md` (active only)

## Tier 3 — On Demand
10–15. Same as Claude protocol

## On Session End
1–4. Same as Claude protocol (except agent memory)
```

#### `gemini-bootstrap.md` (Tiered)

```markdown
# Gemini Bootstrap Protocol v2

## Tier 1 — Always
1–6. Same as Codex protocol

## Tier 2 — Task-Matched
7. Load matching rules from `ai/shared/rules/`
8. Discover skills: MANIFEST → ai/shared/skills/ → ai/gemini/.gemini/skills/ → extensions/
9. Read `ai/shared/DECISIONS.md` (active only)

## Tier 3 — On Demand
10–15. Same as Claude protocol

## On Session End
1–4. Same as Codex protocol
```

---

### 4. Skill Manifest — Lazy Loading

> Replaces eager skill loading. The manifest is a lightweight index (~300 tokens) that enables CLIs to load only relevant skills.

#### `ai/shared/skills/MANIFEST.md`

```markdown
# Skill Manifest

| Skill | Trigger Keywords | Path | Est. Tokens |
|-------|-----------------|------|-------------|
| security-review | security, auth, vulnerability, CVE, OWASP | ai/shared/skills/security-review/ | ~3,200 |
| api-design | endpoint, REST, GraphQL, schema, route | ai/shared/skills/api-design/ | ~2,800 |
| db-migration | migration, schema change, ALTER, table | ai/shared/skills/db-migration/ | ~2,500 |
```

**Rules:**
- MANIFEST.md is loaded in Tier 1 (always)
- Individual skills are loaded in Tier 2 (only when trigger keywords match the task)
- `reference.md` within a skill is Tier 3 (only if deep knowledge is needed)
- MANIFEST.md must be updated when skills are added or removed
- Estimated tokens help the CLI stay within budget

---

### 5. Decision Rotation

> Prevents unbounded growth of DECISIONS.md. At ~150 tokens per decision, 30 active decisions ≈ 4,500 tokens (within budget). Beyond that, entries are rotated to an archive.

#### How Rotation Works

1. `max_active_decisions` is set in `harness.json` (default: 30)
2. When a new decision is added and the count exceeds the max:
   - The oldest decision is moved from `DECISIONS.md` to `DECISIONS_ARCHIVE.md`
   - A one-line summary is added/updated in `DECISIONS_INDEX.md`
3. CLIs load `DECISIONS.md` (active) and `DECISIONS_INDEX.md` (summaries) in Tier 2
4. If a CLI detects a potential conflict with an archived decision via the index, it loads the full entry from the archive (Tier 3)

#### `DECISIONS_INDEX.md` Format

```markdown
# Decision Index (Active + Archived)

| ID | Date | Status | Summary |
|----|------|--------|---------|
| DEC-001 | 2025-06-10 | Archived | PostgreSQL over MySQL for primary datastore |
| DEC-002 | 2025-06-12 | Archived | Zod for runtime validation |
| ... | | | |
| DEC-029 | 2025-08-01 | Active | SSE over WebSocket for log streaming |
| DEC-030 | 2025-08-03 | Active | Per-target mutex for concurrent runs |
```

At ~15 tokens per row, 100 decisions = ~1,500 tokens. Much cheaper than 100 full entries (~15,000 tokens).

---

### 6. Claude = Orchestrator Layer

Claude is responsible for agent-based workflows, rule enforcement, memory persistence, and structured execution.

#### Requirements

- `CLAUDE.md` must encode the tiered protocol (directly for single-CLI, via adapter for multi-CLI)
- All shared rules must be loaded in Tier 2 when relevant
- Skills must follow full structure (SKILL.md + checklist + reference + examples)
- Commands must follow schema: Input → Steps → Output → Constraints
- Agent memory must include: MEMORY.md (human), state.json (machine), history.md (logs)

---

### 7. Codex = Execution Layer (Lightweight)

Optimized for fast iteration and shell-driven workflows.

#### Requirements

- `codex.md` must encode the tiered protocol
- Must define: project context, allowed actions, forbidden areas, coding conventions (or pointer to STANDARDS.md)
- Maintain stateless philosophy but rely on shared context
- Reusable layers: `prompts/` (templates), `workflows/` (task flows)

---

### 8. Gemini = Context Discovery + Skill Layer

Operates via automatic project ingestion and multi-tier skill discovery.

#### Requirements

- `GEMINI.md` encodes the tiered protocol
- Skill discovery tiers (in order):
  1. `ai/shared/skills/` via MANIFEST.md — shared, tool-agnostic
  2. `ai/gemini/.gemini/skills/` — Gemini-specific
  3. `ai/gemini/.gemini/extensions/` — plugins/external
- `extensions/` directory must exist for future scalability
- Gemini's 1M context window makes Tier 3 loading less costly, but the tiered protocol should still be followed for consistency

---

### 9. Decision Log (`DECISIONS.md`) — Multi-CLI Only

Append-only (active entries). Rotated to archive when exceeding `max_active_decisions`.

In single-CLI mode this file does not exist — decisions are implicit in the CLI's own memory/history.

#### Format

```markdown
# Decision Log (Active)

## DEC-029 — 2025-08-01 — Claude
**Decision**: Use SSE over WebSocket for log streaming
**Rationale**: Unidirectional, auto-reconnects, works through proxies
**Alternatives Rejected**: WebSocket (bidirectional overkill), polling (latency)
**Status**: Active

## DEC-030 — 2025-08-03 — Codex
**Decision**: Per-target mutex for concurrent runs
**Rationale**: Prevents deploy race conditions without global queue bottleneck
**Alternatives Rejected**: Global queue (unnecessary serialization), no locking (unsafe)
**Status**: Active
```

#### Rules

- Entries are **never deleted**, only superseded (`Supersedes: DEC-XXX`) or rotated to archive
- Every decision must have: ID, date, tool, decision, rationale, alternatives rejected
- All CLIs must read active decisions (Tier 2) before starting work
- The index is always loaded alongside active decisions for conflict detection

---

### 10. Conflict Resolution (`CONFLICT_RESOLUTION.md`) — Multi-CLI Only

This is a **human reference document** — it is NOT loaded by CLIs on bootstrap. The bootstrap adapters encode the precedence rules directly.

#### Precedence Order (highest → lowest)

1. `ai/shared/CONSTRAINTS.md` — absolute boundaries
2. `ai/shared/STANDARDS.md` — coding conventions
3. `ai/shared/rules/*` — domain-specific rules
4. `ai/shared/DECISIONS.md` — settled decisions
5. Tool-specific overrides (e.g., `.claude/rules/`) — **only if explicitly justified**

#### Rules

- Shared context **always** wins over tool-specific config
- Tool-specific overrides must include a `justification` comment
- If two tools produce conflicting outputs, the shared constraints are the tiebreaker
- Unknown situations default to the most restrictive interpretation

---

### 11. Skills = Core Reusability Unit

All skills (across all CLIs) must include:

| File | Purpose | Required | Bootstrap Tier |
|------|---------|----------|---------------|
| `SKILL.md` | Execution logic & instructions | Yes | Tier 2 |
| `checklist.md` | Validation steps | Yes | Tier 2 |
| `reference.md` | Deep domain knowledge | Yes | Tier 3 |
| `examples.md` | Usage patterns & samples | Yes | Tier 3 |

**Without `reference.md` → shallow outputs. Without `checklist.md` → no validation.**

Skills live in `ai/shared/skills/` by default. MANIFEST.md is the discovery mechanism. Tool-specific skills are the exception, not the norm.

---

### 12. Rules = Enforced Constraints

Rules must:

- Live in `ai/shared/rules/` (tool-agnostic)
- Be loaded in Tier 2 when they match the task domain
- Cover at minimum: API design, testing, security, performance, refactoring
- Be actionable (not aspirational) — each rule must be verifiable
- Stay within the `rule_max_tokens` budget (default: 750 tokens per rule file)

#### Rule File Format

```markdown
# Rule: [Name]

## Scope
What this rule applies to. Keywords for Tier 2 matching.

## Requirements
- MUST: [hard requirement]
- MUST NOT: [forbidden action]
- SHOULD: [strong recommendation]

## Verification
How to check compliance (automated or manual).

## Examples
Good and bad examples.
```

---

### 13. Agents = Cross-Tool Concept

Even though only Claude natively supports agents, `AGENTS.md` defines the mental model all CLIs follow.

| Role | Responsibility | Native Support |
|------|---------------|----------------|
| Planner | Breaks tasks into steps, sequences work | Claude |
| Executor | Writes code, runs commands | All |
| Reviewer | Validates output against rules/checklists | Claude |
| Researcher | Gathers context, reads docs | Gemini |

Agents must not exceed their defined scope. Agent state is persisted only by Claude; other CLIs are stateless. `AGENTS.md` is Tier 3 — only loaded when orchestration is relevant.

---

### 14. Memory Strategy

| Type | Tool | Location | Present When | Bootstrap Tier |
|------|------|----------|--------------|---------------|
| Persistent | Claude | `agent-memory/` | Claude active | Tier 2 (state only) |
| Session/Handoff | All | `session-state.json` + `SESSION.md` | Multi-CLI | Tier 1 |
| Decision (active) | All | `DECISIONS.md` | Multi-CLI | Tier 2 |
| Decision (archive) | All | `DECISIONS_ARCHIVE.md` | Multi-CLI | Tier 3 |
| Decision (index) | All | `DECISIONS_INDEX.md` | Multi-CLI | Tier 2 |
| Replay | Codex | `.codex/history/` | Codex active | Not loaded (local tool) |
| Snapshot | Gemini | `.gemini/cache/` | Gemini active | Not loaded (local tool) |

---

### 15. MCP Configuration

`.mcp.json` at project root is the shared MCP server config.

- **Claude**: Native MCP support — reads `.mcp.json` automatically
- **Codex**: `codex.md` must include directive to respect MCP config
- **Gemini**: `GEMINI.md` must include directive to read `.mcp.json` and map to extensions

Only relevant if the active CLI supports or benefits from MCP.

---

### 16. Git Strategy

#### Always Committed

- `ai/harness.json`
- `ai/shared/*` (core docs, rules, skills, manifest, decisions, index, archive)
- Active CLI instruction files and config
- `ai/adapters/*` (if multi-CLI)
- `.mcp.json`

#### Always Gitignored

```gitignore
# Local overrides
ai/claude/.claude/settings.local.json

# Ephemeral caches
ai/codex/.codex/cache/
ai/gemini/.gemini/cache/

# Session replay (large, local-only)
ai/codex/.codex/history/
```

#### Team Decision (document in harness.json)

- `ai/shared/session-state.json` — commit for async team handoff, gitignore for solo dev
- `ai/claude/.claude/agent-memory/*/state.json` — commit for persistence across machines

---

### 17. Scaling: Adding a CLI Later

When you start with Claude-only and later want to add Gemini:

1. Create `ai/gemini/` with `GEMINI.md` and `.gemini/` structure
2. Update `ai/harness.json`: `active_harnesses: ["claude", "gemini"]`, `handoff_enabled: true`
3. Create `ai/adapters/` with `claude-bootstrap.md` and `gemini-bootstrap.md`
4. Create handoff files: `SESSION.md`, `session-state.json`, `DECISIONS.md`, `DECISIONS_INDEX.md`, `DECISIONS_ARCHIVE.md`, `CONFLICT_RESOLUTION.md`
5. Update `CLAUDE.md` to reference bootstrap adapter instead of direct tiered protocol

**Core shared files (CONSTRAINTS, STANDARDS, etc.) are untouched.** Only the wiring changes.

### Scaling: Removing a CLI

1. Delete the CLI's folder (e.g., `ai/codex/`)
2. Remove from `ai/harness.json`
3. If back to single CLI: delete `ai/adapters/`, remove handoff files, update remaining CLI's instruction file to encode tiered protocol directly
4. Set `handoff_enabled: false` in `harness.json`

---

## Token Budget Governance

### Recommended Maximums

| Component | Max Tokens | Enforcement |
|-----------|-----------|-------------|
| Tier 1 bootstrap (always loaded) | 5,000 | Hard budget in harness.json |
| Any single core doc | 1,500 | Convention — refactor if exceeded |
| Any single rule file | 750 | Convention — split if exceeded |
| Skill manifest (MANIFEST.md) | 500 | Convention |
| Single skill (SKILL.md + checklist.md) | 2,000 | Convention — Tier 2 load |
| Single skill (full, including reference.md) | 4,000 | Convention — Tier 3 full load |
| Active decisions (≤30 entries) | 4,500 | Auto-rotation enforced |
| Decision index (all entries) | 1,500 | Convention |
| Session state (json + md) | 1,500 | Convention |
| Total bootstrap (typical task, T1+T2) | 8,000–12,000 | Governance target |
| Total bootstrap ceiling (complex task, all tiers) | 25,000 | Hard alarm — investigate if exceeded |

### Context Utilization Targets

| CLI | Context Window | Bootstrap Target | Max Acceptable | Notes |
|-----|---------------|-----------------|----------------|-------|
| Claude (200K) | < 5% (~10K) | < 10% (~20K) | 12.5% (~25K) | |
| Codex (200K) | < 5% (~10K) | < 10% (~20K) | 12.5% (~25K) | |
| Gemini (1M) | < 1% (~10K) | < 2% (~20K) | 2.5% (~25K) | Larger window = more headroom |

---

## Edge Cases & Risks

### Risk: CLI Doesn't Support Lazy Loading

**Problem**: Codex and Gemini may not support conditional file loading — they may ingest everything in their context.

**Mitigation**: For CLIs without conditional loading, the bootstrap adapter lists only Tier 1 files as explicit references. Tier 2/3 files are loaded via inline instructions ("if the task involves security, read `ai/shared/rules/security.md`"). Gemini's 1M context makes eager loading less painful.

**Fallback**: Accept eager Tier 1 + Tier 2 loading for Codex/Gemini; reserve Tier 3 laziness for Claude.

### Risk: Decision Archive Loses Context

**Problem**: Rotating decisions to an archive means a CLI might contradict an archived decision it didn't read.

**Mitigation**: `DECISIONS_INDEX.md` provides one-line summaries of all decisions (~15 tokens each). The CLI loads the index in Tier 2 and can pull full entries from the archive (Tier 3) if a conflict is detected.

### Risk: Skill Manifest Gets Stale

**Problem**: Someone adds a skill folder but forgets to update `MANIFEST.md`.

**Mitigation**: Add a validation step to Phase 6 tasks. Can be automated with a shell script that compares MANIFEST entries to actual skill directories.

### Risk: Multiple CLIs Writing Session State Simultaneously

**Problem**: In a team setting, two developers might run different CLIs at the same time on the same branch.

**Mitigation**: `session-state.json` includes a `session_id` (UUID). If a CLI reads a session ID that differs from the one it wrote, it knows another session intervened. Resolution: merge or prompt the user.

### Risk: Bootstrap Adapter Drift

**Problem**: The tiered bootstrap references directories, but if rules/skills change, the adapter may have stale assumptions.

**Mitigation**: Adapters reference directories (`ai/shared/rules/`), not individual files. The CLI scans the directory at runtime. The manifest handles skills. Adapters should rarely need updating.

### Risk: Core Doc Size Creep

**Problem**: `ARCHITECTURE.md` starts lean but grows as the project matures, silently eroding the token budget.

**Mitigation**: `budgets.core_doc_max_tokens` in `harness.json` sets the governance target. When a doc exceeds its budget, it must be refactored (split, summarized, or moved to a Tier 3 reference appendix). Budget checks should be part of Phase 6 validation.

---

## Implementation Tasks

### Phase 1: Shared Layer (Foundation) — Always Required

- [ ] Create `ai/harness.json` (manifest with budgets)
- [ ] Create `ai/shared/ARCHITECTURE.md` (≤1,500 tokens)
- [ ] Create `ai/shared/DOMAIN.md` (≤1,500 tokens)
- [ ] Create `ai/shared/CONSTRAINTS.md` (≤750 tokens)
- [ ] Create `ai/shared/STANDARDS.md` (≤1,000 tokens)
- [ ] Create `ai/shared/AGENTS.md` (≤750 tokens)
- [ ] Create `ai/shared/rules/` with 5 rule files (≤750 tokens each)
- [ ] Create `ai/shared/skills/MANIFEST.md` (≤500 tokens)
- [ ] Create at least one reference skill with full structure (SKILL + checklist + reference + examples, ≤4,000 tokens total)

### Phase 2: Handoff Layer — Only If Multi-CLI

- [ ] Create `ai/shared/DECISIONS.md` (empty template)
- [ ] Create `ai/shared/DECISIONS_INDEX.md` (empty template)
- [ ] Create `ai/shared/DECISIONS_ARCHIVE.md` (empty template)
- [ ] Create `ai/shared/SESSION.md` (empty template)
- [ ] Create `ai/shared/session-state.json` (empty schema)
- [ ] Create `ai/shared/CONFLICT_RESOLUTION.md` (human reference — not loaded on boot)
- [ ] Create `ai/adapters/claude-bootstrap.md` (tiered v2)
- [ ] Create `ai/adapters/codex-bootstrap.md` (tiered v2)
- [ ] Create `ai/adapters/gemini-bootstrap.md` (tiered v2)

### Phase 3: Claude — If Opted In

- [ ] Create `CLAUDE.md` (tiered direct for single-CLI, bootstrap for multi)
- [ ] Configure `.claude/settings.json`
- [ ] Implement `.claude/rules/` (Claude-specific overrides only, with justifications)
- [ ] Implement `.claude/tools/`
- [ ] Expand `.claude/skills/` (Claude-specific only)
- [ ] Standardize `.claude/commands/` (Input → Steps → Output → Constraints)
- [ ] Implement `.claude/agents/` with persona definitions
- [ ] Implement `.claude/agent-memory/` with MEMORY.md + state.json + history.md

### Phase 4: Codex — If Opted In

- [ ] Create `codex.md` (tiered direct for single-CLI, bootstrap for multi)
- [ ] Configure `.codex/config.json`
- [ ] Add `.codex/prompts/` with reusable templates
- [ ] Add `.codex/workflows/` with structured task flows

### Phase 5: Gemini — If Opted In

- [ ] Create `GEMINI.md` (tiered direct for single-CLI, bootstrap for multi)
- [ ] Configure `.gemini/config.json`
- [ ] Add `.gemini/skills/` (Gemini-specific only)
- [ ] Add `.gemini/extensions/` directory

### Phase 6: Integration, Validation & Budget Verification

- [ ] Measure actual token counts for all shared files — verify within budgets
- [ ] Verify MANIFEST.md matches actual skill directories
- [ ] Test Tier 1 bootstrap token count (target: <5,000)
- [ ] Test full T1+T2 bootstrap token count (target: <12,000)
- [ ] Test worst-case T1+T2+T3 token count (ceiling: <25,000)
- [ ] Test handoff: CLI A → CLI B (verify session state pickup)
- [ ] Test handoff: CLI B → CLI A (full round-trip)
- [ ] Test decision rotation (add 35 decisions, verify archive + index)
- [ ] Validate consistent outputs across active CLIs for same task
- [ ] Verify decision log is respected across switches
- [ ] Verify conflict resolution precedence works in practice
- [ ] Configure `.gitignore` for ephemeral vs committed files
- [ ] Create budget check script (compares file sizes to harness.json budgets)
- [ ] Document usage, profiles, tiered protocol, scaling, and budgets in README

---

## Acceptance Criteria

### All Profiles

- [ ] `harness.json` accurately reflects active CLIs, handoff state, and budgets
- [ ] Shared context is enforced across all active tools
- [ ] Skills are discoverable via MANIFEST.md and loaded lazily
- [ ] Rules follow standard format (Scope → Requirements → Verification → Examples)
- [ ] Git strategy clearly separates committed vs ephemeral files
- [ ] MCP config is discoverable by all active CLIs
- [ ] **Tier 1 bootstrap consumes <5,000 tokens**
- [ ] **Typical task bootstrap (T1+T2) consumes <12,000 tokens (<6% of 200K)**
- [ ] **Worst-case bootstrap (all tiers) does not exceed 25,000 tokens (<12.5% of 200K)**
- [ ] **No single shared file exceeds its token budget**

### Single-CLI Profile

- [ ] No adapter, handoff, or multi-CLI files exist in the project
- [ ] CLI reads shared context via tiered protocol directly
- [ ] Adding a second CLI later works by following the scaling guide

### Multi-CLI Profile

- [ ] CLI switching works without modifying core shared files
- [ ] A CLI started mid-project picks up full context from previous session
- [ ] Decisions are never re-litigated after switching tools
- [ ] Decision rotation works correctly at the threshold
- [ ] Agent workflows are consistent and predictable
- [ ] Round-trip handoff (CLI A → CLI B → CLI A) works end-to-end
- [ ] Removing a CLI cleanly reverts to single-CLI mode

---

## Expected Outcome

A modular AI harness that enables:

- **Opt-in** — only install CLIs you use; no folder bloat
- **Scalable** — add or remove CLIs without touching core context
- **Deterministic** — shared rules and constraints enforced everywhere
- **Interchangeable** — zero-friction CLI switching when multi-CLI
- **Traceable** — decisions and session history survive tool switches
- **Composable** — reusable skills, commands, and workflows
- **Efficient** — tiered bootstrap keeps context usage under 5% for typical tasks

The harness — not the tool — owns the context.
