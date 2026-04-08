# AI Harness — Token Cost & Efficiency Analysis

## Methodology

- Token estimates use the ~4 characters = 1 token approximation
- Claude context: 200K tokens; Codex: 200K tokens; Gemini: 1M+ tokens
- Costs based on Claude Sonnet input pricing (~$3/MTok) as reference
- All estimates are for the **bootstrap/init sequence** — the context consumed before the CLI does any actual work

---

## 1. File Size Estimates (Realistic Content)

### Shared Layer — Core Docs

| File | Estimated Size | Tokens | Notes |
|------|---------------|--------|-------|
| `ARCHITECTURE.md` | 3–6 KB | 750–1,500 | Component map, data flow, diagrams |
| `DOMAIN.md` | 2–5 KB | 500–1,250 | Ubiquitous language, bounded contexts |
| `CONSTRAINTS.md` | 1–3 KB | 250–750 | Hard boundaries, forbidden actions |
| `STANDARDS.md` | 2–4 KB | 500–1,000 | Naming, formatting, patterns |
| `AGENTS.md` | 1–3 KB | 250–750 | Roles, responsibilities |
| **Subtotal (core)** | **9–21 KB** | **2,250–5,250** | |

### Shared Layer — Rules

| File | Estimated Size | Tokens | Notes |
|------|---------------|--------|-------|
| `api-design.md` | 1–3 KB | 250–750 | |
| `testing.md` | 1–3 KB | 250–750 | |
| `security.md` | 1–3 KB | 250–750 | |
| `performance.md` | 1–2 KB | 250–500 | |
| `refactoring.md` | 1–2 KB | 250–500 | |
| **Subtotal (rules)** | **5–13 KB** | **1,250–3,250** | |

### Shared Layer — Skills (per skill)

| File | Estimated Size | Tokens | Notes |
|------|---------------|--------|-------|
| `SKILL.md` | 1–3 KB | 250–750 | |
| `checklist.md` | 0.5–2 KB | 125–500 | |
| `reference.md` | 2–8 KB | 500–2,000 | This is the heavy one |
| `examples.md` | 1–4 KB | 250–1,000 | |
| **Subtotal (1 skill)** | **4.5–17 KB** | **1,125–4,250** | |
| **3 skills** | **13.5–51 KB** | **3,375–12,750** | |
| **5 skills** | **22.5–85 KB** | **5,625–21,250** | |

### Handoff Layer (Multi-CLI Only)

| File | Estimated Size | Tokens | Notes |
|------|---------------|--------|-------|
| `SESSION.md` | 0.5–2 KB | 125–500 | Grows with session complexity |
| `session-state.json` | 0.5–2 KB | 125–500 | |
| `DECISIONS.md` | 0.5–20 KB | 125–5,000 | **Grows unbounded over time** |
| `HANDOFF_PROTOCOL.md` | 1–2 KB | 250–500 | Static, read once |
| `CONFLICT_RESOLUTION.md` | 0.5–1 KB | 125–250 | Static, read once |
| Bootstrap adapter | 0.5–1 KB | 125–250 | Per CLI |
| **Subtotal (handoff)** | **3.5–28 KB** | **875–7,000** | |

### CLI-Specific Instruction Files

| File | Estimated Size | Tokens | Notes |
|------|---------------|--------|-------|
| `CLAUDE.md` | 1–3 KB | 250–750 | |
| `codex.md` | 1–2 KB | 250–500 | |
| `GEMINI.md` | 1–2 KB | 250–500 | |
| `harness.json` | 0.2–0.5 KB | 50–125 | |

---

## 2. Bootstrap Cost by Scenario

### Scenario A: Single CLI — Claude-Only (Fresh Project, 1 Skill)

```
What gets loaded:
  harness.json ................ ~75 tokens
  CLAUDE.md ................... ~500 tokens
  ARCHITECTURE.md ............. ~1,000 tokens
  DOMAIN.md ................... ~750 tokens
  CONSTRAINTS.md .............. ~500 tokens
  STANDARDS.md ................ ~750 tokens
  AGENTS.md ................... ~500 tokens
  rules/ (5 files) ........... ~1,750 tokens
  skills/ (1 skill) .......... ~2,000 tokens
                                ─────────────
  TOTAL BOOTSTRAP            ~7,825 tokens
```

| Metric | Value |
|--------|-------|
| **Bootstrap tokens** | ~7,825 |
| **% of 200K context** | **3.9%** |
| **Cost per init** | **$0.023** |
| **Verdict** | ✅ Lightweight — no concerns |

### Scenario B: Single CLI — Claude-Only (Mature Project, 5 Skills)

```
What gets loaded:
  harness.json ................ ~75 tokens
  CLAUDE.md ................... ~750 tokens
  Core docs (5 files) ........ ~4,000 tokens
  rules/ (5 files) ........... ~2,500 tokens
  skills/ (5 skills) ......... ~15,000 tokens
  agent-memory state ......... ~500 tokens
                                ─────────────
  TOTAL BOOTSTRAP            ~22,825 tokens
```

| Metric | Value |
|--------|-------|
| **Bootstrap tokens** | ~22,825 |
| **% of 200K context** | **11.4%** |
| **Cost per init** | **$0.068** |
| **Verdict** | ⚠️ Acceptable but skills are eating context — see optimization section |

### Scenario C: Multi-CLI — Claude + Gemini (Fresh, 1 Skill)

```
What Claude loads:
  harness.json ................ ~75 tokens
  claude-bootstrap.md ......... ~200 tokens
  CLAUDE.md ................... ~500 tokens
  session-state.json .......... ~300 tokens
  SESSION.md .................. ~300 tokens
  DECISIONS.md ................ ~200 tokens
  HANDOFF_PROTOCOL.md ......... ~375 tokens
  CONFLICT_RESOLUTION.md ...... ~200 tokens
  Core docs (5 files) ........ ~3,250 tokens
  rules/ (5 files) ........... ~1,750 tokens
  skills/ (1 skill) .......... ~2,000 tokens
                                ─────────────
  TOTAL BOOTSTRAP            ~9,150 tokens
```

| Metric | Value |
|--------|-------|
| **Bootstrap tokens** | ~9,150 |
| **% of 200K context** | **4.6%** |
| **Additional cost vs single-CLI** | **+$0.004** (handoff layer adds ~1,325 tokens) |
| **Verdict** | ✅ Minimal overhead for handoff capability |

### Scenario D: Multi-CLI — Full Trio (Mature, 5 Skills, 20 Decisions)

```
What each CLI loads:
  harness.json ................ ~75 tokens
  bootstrap adapter ........... ~200 tokens
  CLI instruction file ........ ~500–750 tokens
  session-state.json .......... ~500 tokens
  SESSION.md .................. ~500 tokens
  DECISIONS.md (20 entries) ... ~3,000 tokens    ← GROWING
  HANDOFF_PROTOCOL.md ......... ~375 tokens
  CONFLICT_RESOLUTION.md ...... ~200 tokens
  Core docs (5 files) ........ ~4,000 tokens
  rules/ (5 files) ........... ~2,500 tokens
  skills/ (5 skills) ......... ~15,000 tokens    ← HEAVY
                                ─────────────
  TOTAL BOOTSTRAP            ~26,850–27,100 tokens
```

| Metric | Value |
|--------|-------|
| **Bootstrap tokens** | ~27,000 |
| **% of 200K context (Claude/Codex)** | **13.5%** |
| **% of 1M context (Gemini)** | **2.7%** |
| **Cost per init (Claude pricing)** | **$0.081** |
| **Verdict** | ⚠️ Getting heavy — DECISIONS.md and skills need management |

### Scenario E: Multi-CLI — Full Trio (Long-Running, 5 Skills, 50 Decisions)

```
  DECISIONS.md (50 entries) ... ~7,500 tokens    ← PROBLEM
  skills/ (5 skills) ......... ~15,000 tokens
  everything else ............. ~9,350 tokens
                                ─────────────
  TOTAL BOOTSTRAP            ~31,850 tokens
```

| Metric | Value |
|--------|-------|
| **Bootstrap tokens** | ~31,850 |
| **% of 200K context** | **15.9%** |
| **Cost per init** | **$0.096** |
| **Verdict** | 🔴 Approaching danger zone — 1/6 of context consumed before any work |

### Scenario F: Worst Case — Full Trio, 10 Skills, 100 Decisions, Verbose Docs

```
  Core docs (verbose) ......... ~5,250 tokens
  rules/ (5 files, verbose) .. ~3,250 tokens
  skills/ (10 skills) ........ ~30,000 tokens    ← DOMINANT COST
  DECISIONS.md (100 entries) .. ~15,000 tokens   ← UNBOUNDED GROWTH
  handoff + session ........... ~2,500 tokens
  harness + bootstrap + CLI ... ~1,000 tokens
                                ─────────────
  TOTAL BOOTSTRAP            ~57,000 tokens
```

| Metric | Value |
|--------|-------|
| **Bootstrap tokens** | ~57,000 |
| **% of 200K context** | **28.5%** |
| **Cost per init** | **$0.171** |
| **Verdict** | 🔴 CRITICAL — nearly 1/3 of context gone on bootstrap |

---

## 3. Handoff Cost (Switching Between CLIs)

The cost of a handoff = the cost of the new CLI's bootstrap (since the previous CLI's context is discarded).

| Switch | Extra Work Beyond Bootstrap | Cost |
|--------|---------------------------|------|
| Claude → Gemini | Gemini reads same shared layer + session state | ~$0 extra (just bootstrap) |
| Gemini → Codex | Same | ~$0 extra |
| Codex → Claude | Same + Claude loads agent memory | +~$0.002 (agent state) |
| Any → Any | **No extra cost** — it's just a fresh bootstrap | Bootstrap cost only |

**Key insight**: Handoff cost = bootstrap cost. There's no additional "switching tax." The only cost is the new CLI consuming the shared context, which it would do anyway on a fresh start.

### Handoff Frequency Cost (Per Day)

| Switches/Day | Scenario B (single) | Scenario D (multi) | Scenario F (worst) |
|-------------|--------------------|--------------------|-------------------|
| 1 | $0.068 | $0.081 | $0.171 |
| 3 | $0.204 | $0.243 | $0.513 |
| 5 | $0.340 | $0.405 | $0.855 |
| 10 | $0.680 | $0.810 | $1.710 |

These are **input-only** costs. Actual session costs (responses, tool use, iteration) will be 10–50x higher, making bootstrap costs negligible in practice.

---

## 4. Identified Problems

### PROBLEM 1: `DECISIONS.md` Grows Unbounded

**Severity**: 🔴 Critical

The decision log is append-only by design. At ~150 tokens per decision entry:
- 10 decisions = ~1,500 tokens (fine)
- 50 decisions = ~7,500 tokens (concerning)
- 100 decisions = ~15,000 tokens (7.5% of context just for decisions)
- 200 decisions = ~30,000 tokens (15% of context — unacceptable)

**Impact**: Every CLI loads the full decision log on every session start. Old, irrelevant decisions waste context.

### PROBLEM 2: Skills Are the Dominant Cost

**Severity**: ⚠️ High

A single skill with `reference.md` can consume 2,000–4,250 tokens. With 5–10 skills, this becomes 10K–42K tokens — the largest single cost component.

**Impact**: Not every task needs every skill. Loading all skills on every bootstrap is wasteful.

### PROBLEM 3: Redundant Static Docs on Every Init

**Severity**: ⚠️ Medium

`HANDOFF_PROTOCOL.md` and `CONFLICT_RESOLUTION.md` are static documents that explain *how* the harness works. The CLI doesn't need to re-read these every session — they're operational guides, not context.

**Impact**: ~500–750 wasted tokens per init.

### PROBLEM 4: Core Docs May Bloat Over Time

**Severity**: ⚠️ Medium

`ARCHITECTURE.md` starts lean but tends to grow as the project matures. A 15 KB architecture doc = ~3,750 tokens.

**Impact**: Gradual context erosion that's hard to notice.

### PROBLEM 5: No Lazy Loading — Everything is Eager

**Severity**: 🔴 Critical (Architectural)

The current bootstrap protocol says "load everything." There's no mechanism for a CLI to load only what's relevant to the current task.

**Impact**: The cost ceiling is always the worst case for that profile, regardless of task complexity.

---

## 5. Proposed Optimizations

### OPT-1: Decision Log Rotation

**Fixes**: Problem 1

Add a `max_active_decisions` field to `harness.json`. When the log exceeds this threshold, older decisions are moved to `DECISIONS_ARCHIVE.md` (committed but not loaded on bootstrap).

```json
{
  "handoff": {
    "max_active_decisions": 30
  }
}
```

Bootstrap protocol change: CLIs load only `DECISIONS.md` (active), not the archive. If a CLI needs historical context, it can read the archive on demand.

**Token savings**: Caps decision cost at ~4,500 tokens regardless of project age.

### OPT-2: Skill Lazy Loading (Task-Based)

**Fixes**: Problem 2

Instead of loading all skills on bootstrap, load only the skill manifest and let the CLI pull skills on demand.

Add `ai/shared/skills/MANIFEST.md`:

```markdown
# Skill Manifest

| Skill | Trigger Keywords | Path |
|-------|-----------------|------|
| security-review | security, auth, vulnerability, CVE | ai/shared/skills/security-review/ |
| api-design | endpoint, REST, GraphQL, schema | ai/shared/skills/api-design/ |
| db-migration | migration, schema change, ALTER | ai/shared/skills/db-migration/ |
```

Bootstrap protocol change: CLIs load only `MANIFEST.md` (~200–500 tokens). When a task matches trigger keywords, the CLI loads that specific skill.

**Token savings**: 3,000–40,000+ tokens per init depending on skill count. Manifest costs ~300 tokens vs 15,000+ for 5 full skills.

### OPT-3: Split Static vs Dynamic Handoff Docs

**Fixes**: Problem 3

Move `HANDOFF_PROTOCOL.md` and `CONFLICT_RESOLUTION.md` out of the bootstrap sequence. These are reference docs for humans setting up the harness, not runtime context for CLIs.

Bootstrap protocol change: Remove these from the "read on init" list. The bootstrap adapter already encodes the protocol — the CLI doesn't need to also read the human-facing explanation.

**Token savings**: ~500–750 tokens per init.

### OPT-4: Core Doc Size Budgets

**Fixes**: Problem 4

Add token budgets to `harness.json`:

```json
{
  "budgets": {
    "core_docs_max_tokens": 5000,
    "rules_max_tokens": 3000,
    "skills_manifest_max_tokens": 500,
    "decisions_max_tokens": 4500,
    "session_state_max_tokens": 1000,
    "total_bootstrap_max_tokens": 15000
  }
}
```

This is a governance mechanism — not enforced by code, but by convention. When a core doc exceeds its budget, it must be refactored (split, summarized, or moved to reference).

### OPT-5: Tiered Bootstrap Protocol

**Fixes**: Problem 5 (the big one)

Replace the flat "load everything" bootstrap with a tiered approach:

```
TIER 1 — Always loaded (~3,000–5,000 tokens)
  harness.json
  CLI instruction file
  CONSTRAINTS.md (hard boundaries — always needed)
  STANDARDS.md (coding conventions — always needed)
  session-state.json (if multi-CLI)
  SESSION.md (if multi-CLI)
  Skill MANIFEST.md (index only)

TIER 2 — Loaded on task match (~2,000–5,000 tokens)
  Relevant rules (matched by task type)
  Relevant skills (matched by MANIFEST triggers)
  DECISIONS.md (only active decisions)

TIER 3 — Loaded on demand (~1,000–5,000 tokens)
  ARCHITECTURE.md (when task involves system design)
  DOMAIN.md (when task involves business logic)
  AGENTS.md (when task involves multi-agent orchestration)
  Skill reference.md (deep dive only when needed)
  DECISIONS_ARCHIVE.md (historical lookup)
```

Updated bootstrap adapter:

```markdown
# Claude Bootstrap Protocol v2

## Tier 1 — Always (do this first)
1. Read `ai/harness.json`
2. Read `ai/shared/CONSTRAINTS.md`
3. Read `ai/shared/STANDARDS.md`
4. Read `ai/shared/skills/MANIFEST.md`
5. If multi-CLI: read `session-state.json` + `SESSION.md`

## Tier 2 — Task-Matched (do this after reading the user's request)
6. Load rules matching the task domain from `ai/shared/rules/`
7. Load skills matching MANIFEST triggers
8. Read `ai/shared/DECISIONS.md` (active only)

## Tier 3 — On Demand (only if the task requires it)
9. `ARCHITECTURE.md` — if task involves system design or component changes
10. `DOMAIN.md` — if task involves business logic or domain modeling
11. `AGENTS.md` — if task involves orchestration or agent coordination
12. Skill `reference.md` — if deep domain knowledge is needed
```

---

## 6. Optimized Cost Comparison

### Scenario D Revisited: Full Trio, 5 Skills, 20 Decisions

| | Before Optimization | After Optimization | Savings |
|---|---|---|---|
| **Tier 1 (always)** | — | ~3,500 tokens | — |
| **Tier 2 (task-matched, ~2 rules + 1 skill)** | — | ~4,000 tokens | — |
| **Total loaded** | ~27,000 tokens | ~7,500 tokens | **72% reduction** |
| **% of 200K context** | 13.5% | 3.75% | |
| **Cost per init** | $0.081 | $0.023 | **$0.058 saved** |

### Scenario F Revisited: Full Trio, 10 Skills, 100 Decisions

| | Before Optimization | After Optimization | Savings |
|---|---|---|---|
| **Total loaded** | ~57,000 tokens | ~8,500 tokens | **85% reduction** |
| **% of 200K context** | 28.5% | 4.25% | |
| **Cost per init** | $0.171 | $0.026 | **$0.145 saved** |

### Daily Cost at 5 Switches/Day

| Scenario | Before | After | Monthly Savings (22 workdays) |
|----------|--------|-------|-------------------------------|
| B (single, 5 skills) | $0.340 | $0.115 | $4.95 |
| D (multi, 5 skills, 20 dec) | $0.405 | $0.115 | $6.38 |
| F (worst case) | $0.855 | $0.130 | $15.95 |

---

## 7. Token Budget Summary (Optimized)

### Recommended Maximums

| Component | Max Tokens | Enforcement |
|-----------|-----------|-------------|
| Tier 1 bootstrap (always loaded) | 5,000 | Hard budget in harness.json |
| Any single core doc | 1,500 | Convention — refactor if exceeded |
| Any single rule file | 750 | Convention |
| Skill manifest (index) | 500 | Convention |
| Single skill (full load) | 4,000 | Convention — split if exceeded |
| Active decisions | 4,500 (~30 entries) | Auto-rotation to archive |
| Session state (json + md) | 1,500 | Convention |
| Total bootstrap (all tiers, typical task) | 12,000–15,000 | Governance target |
| Total bootstrap ceiling (complex task) | 25,000 | Hard alarm — investigate |

### Context Utilization Targets

| CLI | Context Window | Bootstrap Target | Max Acceptable |
|-----|---------------|-----------------|----------------|
| Claude (200K) | < 5% (10K) | < 10% (20K) | 12.5% (25K) |
| Codex (200K) | < 5% (10K) | < 10% (20K) | 12.5% (25K) |
| Gemini (1M) | < 1% (10K) | < 2% (20K) | 2.5% (25K) |

---

## 8. Edge Cases & Risks

### Risk: CLI Doesn't Support Lazy Loading

**Problem**: Codex and Gemini may not support "read this file only if the task matches X." They may just ingest everything in their context window.

**Mitigation**: For CLIs without conditional loading, use the bootstrap adapter to pre-filter. The adapter itself can say "For this session, load rules X and Y, skip Z" — but this requires the adapter to be updated per-session or use the task description from `session-state.json` to determine relevance.

**Fallback**: Accept eager loading for Codex/Gemini but keep the tiered approach for Claude. Gemini's 1M context makes this less painful anyway.

### Risk: Decision Archive Loses Context

**Problem**: Rotating old decisions to an archive means a CLI might make a choice that contradicts an archived decision it didn't read.

**Mitigation**: When archiving a decision, add a one-line summary to a `DECISIONS_INDEX.md` (~5 tokens per entry). The CLI loads the index and can pull the full archive entry if a conflict is detected.

### Risk: Skill Manifest Gets Stale

**Problem**: If someone adds a skill folder but forgets to update `MANIFEST.md`, the CLI won't discover it.

**Mitigation**: Add a validation step to Phase 6 tasks: "Verify MANIFEST.md matches actual skill directories." Can be automated with a simple shell script.

### Risk: Multiple CLIs Writing Session State Simultaneously

**Problem**: In a team setting, two developers might run different CLIs at the same time on the same branch.

**Mitigation**: `session-state.json` should include a `session_id` (UUID). If a CLI reads a session ID that differs from the one it wrote, it knows another session intervened. Resolution: merge or prompt the user.

### Risk: Bootstrap Adapter Drift

**Problem**: The tiered bootstrap is encoded in the adapter file. If shared docs change (new rule added, skill removed), the adapter may not reflect this.

**Mitigation**: Adapters should reference directories (`ai/shared/rules/`), not individual files. The CLI scans the directory at runtime. The manifest handles skills.

---

## 9. Recommendations for the Issue

Based on this analysis, the following changes should be incorporated into the GitHub issue:

1. **Add `harness.json` budget fields** — governance mechanism for token limits
2. **Add `MANIFEST.md` to skills** — index-based skill discovery instead of eager loading
3. **Add decision rotation** — `max_active_decisions` with archive mechanism
4. **Replace flat bootstrap with tiered protocol** — Tier 1/2/3 loading
5. **Remove static docs from bootstrap** — `HANDOFF_PROTOCOL.md` and `CONFLICT_RESOLUTION.md` are human reference, not CLI context
6. **Add token budget targets** to acceptance criteria
7. **Add validation task** — "Verify bootstrap token count is within budget" in Phase 6
