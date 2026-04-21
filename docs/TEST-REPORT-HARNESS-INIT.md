# Test Report — AgentFactory Harness Init in Real-World Repo
<!-- version: 1.0.0 -->

**Date:** 2026-04-21
**Repo under test:** `agentfactory-webapp` (private, `~/repo/agentfactory-webapp`)
**CLI version:** `agentfactory-gen` v0.3.2 (installed from `AgentFactory` source)
**Commands run:**
1. `agentfactory-gen init` (fresh repo, no `.ai/` present)
2. `agentfactory-gen brief` (immediately after init)

---

## Scenario

This test was triggered as part of separating the AgentFactory monorepo into a public
CLI repo and a private webapp repo. After cloning `agentfactory-webapp` to `~/repo/`,
`agentfactory-gen init` was run to give the webapp repo the same AI-assisted development
capabilities as the CLI repo. This is the first real-world test of `init` on a repo that:

- Already had source files (`src/`, `package.json`, etc.) — **not a blank slate**
- Already had a `README.md` with substantial content
- Had no prior `.ai/` directory
- Had no `CLAUDE.md`, `AGENTS.md`, or `GEMINI.md`

---

## Command 1 — `agentfactory-gen init`

### Trigger

```
cd ~/repo/agentfactory-webapp
agentfactory-gen init
```

No flags passed. Default primary adapter: `claude`.

### Execution flow

```
  agentfactory-gen init
  │
  ├─► Step 1 — Create .ai/ directory tree (8 subdirs)
  │     .ai/adapters/claude/    ✓ created + .gitkeep
  │     .ai/adapters/gemini/    ✓ created + .gitkeep
  │     .ai/adapters/codex/     ✓ created + .gitkeep
  │     .ai/rules/              ✓ created + .gitkeep
  │     .ai/commands/           ✓ created + .gitkeep
  │     .ai/skills/             ✓ created + .gitkeep
  │     .ai/agents/             ✓ created + .gitkeep
  │     .ai/memory/             ✓ created + .gitkeep
  │
  ├─► Step 2 — Scaffold .ai/memory/milestones.md
  │     ✓ created (empty traceability matrix template)
  │
  ├─► Step 3a — Create .ai/AgentFactory.md (source of truth)
  │     ✓ created with @agent-registry + @skills-registry markers
  │
  ├─► Step 3b — Create .ai/agent-manifest.json
  │     ✓ created  { "factory": "AgentFactory", "agents": {} }
  │
  ├─► Step 4 — Write default adapter config files
  │     .ai/adapters/claude/settings.json  ✓  {}
  │     .ai/adapters/codex/config.toml     ✓  model = "gpt-5.4"
  │     .ai/adapters/gemini/config.json    ✓  {}
  │
  ├─► Step 5a — Librarian._ensure_adapter_wiring()
  │     .ai/adapters/claude/skills    → ../../skills    ✓ symlink
  │     .ai/adapters/claude/commands  → ../../commands  ✓ symlink
  │     .ai/adapters/codex/skills     → ../../skills    ✓ symlink
  │     .ai/adapters/codex/prompts    → ../../commands  ✓ symlink
  │     .ai/adapters/gemini/tools     → ../../skills    ✓ symlink
  │
  ├─► Step 5b — Librarian._compile_adapter_briefs()
  │     .ai/adapters/claude/brief.md   ✓ compiled
  │     .ai/adapters/codex/brief.md    ✓ compiled
  │     .ai/adapters/gemini/brief.md   ✓ compiled
  │
  ├─► Step 6 — Root MD symlinks (PRIMARY adapter only)
  │     cli.py:260 — loops over primary_config["root_files"] only
  │     primary = "claude"  →  root_files = ["CLAUDE.md"]
  │     CLAUDE.md → .ai/adapters/claude/brief.md   ✓ symlink created
  │
  │     ╔══════════════════════════════════════════╗
  │     ║  GAP #1 — Non-primary root symlinks      ║
  │     ║  AGENTS.md  → NOT created  (codex)       ║
  │     ║  CODEX.md   → NOT created  (codex)       ║
  │     ║  GEMINI.md  → NOT created  (gemini)       ║
  │     ╚══════════════════════════════════════════╝
  │
  └─► Step 7 — Root folder symlinks (ALL adapters)
        .claude → .ai/adapters/claude   ✓ symlink
        .codex  → .ai/adapters/codex    ✓ symlink
        .gemini → .ai/adapters/gemini   ✓ symlink
```

### Terminal output (actual)

```
[librarian] Initializing harness at /home/magooo/repo/agentfactory-webapp ...
  [ok] .ai/adapters/claude
  [ok] .ai/adapters/gemini
  [ok] .ai/adapters/codex
  [ok] .ai/rules
  [ok] .ai/commands
  [ok] .ai/skills
  [ok] .ai/agents
  [ok] .ai/memory
  [created] .ai/memory/milestones.md
  [created] .ai/AgentFactory.md
  [created] .ai/agent-manifest.json
  [wired] adapter capability symlinks + compiled briefs
  [linked] CLAUDE.md -> .ai/adapters/claude/brief.md
  [linked] .claude -> .ai/adapters/claude
  [linked] .codex -> .ai/adapters/codex
  [linked] .gemini -> .ai/adapters/gemini

[librarian] Harness ready. Run 'agentfactory-gen deploy <name>' to scaffold your first agent.
```

**Observation:** Output reports `[wired]` and `[linked]` but gives no indication that
`AGENTS.md` / `GEMINI.md` were skipped — the absence is silent.

---

## Command 2 — `agentfactory-gen brief`

### Trigger

Run after manually updating `.ai/AgentFactory.md` with webapp project context.

```
cd ~/repo/agentfactory-webapp
agentfactory-gen brief
```

### Execution flow

```
  agentfactory-gen brief
  │
  ├─► Librarian._compile_adapter_briefs()
  │     Reads .ai/AgentFactory.md as source of truth
  │     .ai/adapters/claude/brief.md   ✓ recompiled
  │     .ai/adapters/codex/brief.md    ✓ recompiled
  │     .ai/adapters/gemini/brief.md   ✓ recompiled
  │
  └─► Librarian.update_harness_files()   ← librarian.py:985
        │
        ├─ Reads .ai/agent-manifest.json → agents = {}
        ├─ Scans .ai/skills/ for skill-manifest.json → none found
        │
        ├─ Builds agent_registry_text   (empty list)
        ├─ Builds skill_registry_text   (empty list)
        │
        ├─ Targets: [".ai/AgentFactory.md", "README.md"]
        │
        ├─► .ai/AgentFactory.md
        │     @agent-registry marker present → replaced  ✓
        │     @skills-registry marker present → replaced ✓
        │
        └─► README.md
              @agent-registry marker ABSENT
                → else branch (librarian.py:1048)
                → appended "## Registered Agents" block  ✓
              @skills-registry marker ABSENT
                → NO else branch  (librarian.py:1051)
                → ✗ silently skipped — marker NOT injected

              ╔══════════════════════════════════════════╗
              ║  GAP #2 — Skills registry not injected  ║
              ║  README.md has @agent-registry ✓        ║
              ║  README.md missing @skills-registry ✗   ║
              ╚══════════════════════════════════════════╝
```

### Terminal output (actual)

```
[ok] .ai/AgentFactory.md
  [ok] .ai/adapters/claude/brief.md  (CLAUDE.md)
  [ok] .ai/adapters/codex/brief.md  (AGENTS.md, CODEX.md)
  [ok] .ai/adapters/gemini/brief.md  (GEMINI.md)

[librarian] Briefs regenerated.
```

**Observation:** `brief` output lists `(AGENTS.md, CODEX.md)` and `(GEMINI.md)` as the
expected root files for those adapters — confirming the CLI knows they should exist, but
`init` never creates them.

---

## Gap #3 — Inherited broken script

### What happened

`scripts/copy-reports.mjs` was part of the original monorepo webapp code and was
carried into the split. It was not touched by `agentfactory-gen init` or `brief`
(expected — it's not a harness concern).

### The problem

```javascript
// scripts/copy-reports.mjs line 11 (original monorepo path):
const src = resolve(__dirname, "../../.ai/reports");
//                              ^^^^^^^^
//                              Assumes .ai/ is 2 levels up (monorepo layout)
//
// Correct path for standalone webapp repo:
const src = resolve(__dirname, "../.ai/reports");
//                              ^^^^^^^
//                              .ai/ is 1 level up (repo root)
```

The script will `ENOENT` if ever run. The harness reports directory would be at
`~/repo/agentfactory-webapp/.ai/reports/` (one level up from `scripts/`), not two.

### Impact

Low — reports are now vendored as static JSON in `src/data/reports/` and
`copy-reports.mjs` was already removed from the `npm run dev`/`build` scripts.
The script is a dead artifact but will silently mislead anyone who runs it manually.

---

## Full Artifact Audit

```
  ┌─────────────────────────────────────┬────────────┬──────────┐
  │  Artifact                            │  Expected  │  Actual  │
  ├─────────────────────────────────────┼────────────┼──────────┤
  │  .ai/ (8 subdirs + .gitkeep)         │  ✓          │  ✓        │
  │  .ai/memory/milestones.md            │  ✓          │  ✓        │
  │  .ai/AgentFactory.md                 │  ✓          │  ✓        │
  │  .ai/agent-manifest.json             │  ✓          │  ✓        │
  │  .ai/adapters/claude/settings.json   │  ✓          │  ✓        │
  │  .ai/adapters/codex/config.toml      │  ✓          │  ✓        │
  │  .ai/adapters/gemini/config.json     │  ✓          │  ✓        │
  │  .ai/adapters/claude/skills  (link)  │  ✓          │  ✓        │
  │  .ai/adapters/claude/commands (link) │  ✓          │  ✓        │
  │  .ai/adapters/codex/skills   (link)  │  ✓          │  ✓        │
  │  .ai/adapters/codex/prompts  (link)  │  ✓          │  ✓        │
  │  .ai/adapters/gemini/tools   (link)  │  ✓          │  ✓        │
  │  .ai/adapters/claude/brief.md        │  ✓          │  ✓        │
  │  .ai/adapters/codex/brief.md         │  ✓          │  ✓        │
  │  .ai/adapters/gemini/brief.md        │  ✓          │  ✓        │
  │  .claude   (folder link)             │  ✓          │  ✓        │
  │  .codex    (folder link)             │  ✓          │  ✓        │
  │  .gemini   (folder link)             │  ✓          │  ✓        │
  │  CLAUDE.md (root md link)            │  ✓          │  ✓        │
  ├─────────────────────────────────────┼────────────┼──────────┤
  │  AGENTS.md (root md link — codex)    │  ✓          │  ✗ GAP   │
  │  CODEX.md  (root md link — codex)    │  ✓          │  ✗ GAP   │
  │  GEMINI.md (root md link — gemini)   │  ✓          │  ✗ GAP   │
  │  README.md @skills-registry marker   │  ✓          │  ✗ GAP   │
  │  scripts/copy-reports.mjs path       │  ../. ai/  │  ✗ BUG   │
  └─────────────────────────────────────┴────────────┴──────────┘
```

---

## Gap Analysis

### GAP #1 — Non-primary adapter root symlinks not created by `init`

**Severity:** HIGH
**Source:** `cli.py:260` — `for root_file in primary_config["root_files"]:`

```
  ┌─ cli.py:252–278  Root symlink creation ──────────────────────────┐
  │                                                                    │
  │  primary_config = _FORMAT_REGISTRY["claude"]                      │
  │  primary_config["root_files"] = ["CLAUDE.md"]                    │
  │                                                                    │
  │  for root_file in ["CLAUDE.md"]:   ← only one item               │
  │      symlink_to(.ai/adapters/claude/brief.md)   ✓                │
  │                                                                    │
  │  _FORMAT_REGISTRY["codex"]["root_files"]  = ["AGENTS.md","CODEX.md"]
  │  _FORMAT_REGISTRY["gemini"]["root_files"] = ["GEMINI.md"]        │
  │                                                                    │
  │  ╔══════════════════════════════════════════════════════════╗    │
  │  ║  These are never iterated — loop is primary-only        ║    │
  │  ║  AGENTS.md / CODEX.md / GEMINI.md never created         ║    │
  │  ╚══════════════════════════════════════════════════════════╝    │
  └────────────────────────────────────────────────────────────────────┘
```

**Impact:** Codex and Gemini users opening the repo have no root-level `AGENTS.md`
or `GEMINI.md` to orient them. They must run `agentfactory-gen adapter add codex`
or `agentfactory-gen adapter add gemini` to get their symlinks — non-obvious.

**Fix path:** Change `cli.py:260` loop to iterate all adapters:

```python
# Current (primary only):
for root_file in primary_config["root_files"]:

# Fix (all adapters):
for _name, _cfg in _FORMAT_REGISTRY.items():
    brief_path = project_path / HARNESS_ROOT / "adapters" / _name / _cfg["output"]
    if not brief_path.exists():
        continue
    for root_file in _cfg["root_files"]:
        link_path = project_path / root_file
        if link_path.exists() or link_path.is_symlink():
            continue
        link_path.symlink_to(f"{HARNESS_ROOT}/adapters/{_name}/{_cfg['output']}")
```

---

### GAP #2 — Skills registry not injected into README.md

**Severity:** MEDIUM
**Source:** `librarian.py:1051` — missing `else` branch

```
  ┌─ librarian.py:1044–1053  update_harness_files() ──────────────────┐
  │                                                                     │
  │  # Agent registry — has fallback for missing marker:               │
  │  if "<!-- @agent-registry:start -->" in content:                   │
  │      content = agent_pattern.sub(agent_registry_text, content)     │
  │  else:                                                              │
  │      content += "\n\n## Registered Agents\n{agent_registry_text}"  │
  │            ↑                                                        │
  │            Always injected, even if marker was absent              │
  │                                                                     │
  │  # Skills registry — NO fallback:                                  │
  │  if "<!-- @skills-registry:start -->" in content:                  │
  │      content = skill_pattern.sub(skill_registry_text, content)     │
  │  # ← no else                                                       │
  │       ↑                                                             │
  │       Silently skipped if marker absent                            │
  │                                                                     │
  │  Result for a new README.md (no markers pre-existing):             │
  │    @agent-registry   → APPENDED  ✓                                 │
  │    @skills-registry  → SKIPPED   ✗                                 │
  └─────────────────────────────────────────────────────────────────────┘
```

**Impact:** When skills are later added with `agentfactory-gen import-skill`, the
project README will auto-update the agents list but never list skills. The skills
list lives only in `.ai/AgentFactory.md`, not in the human-facing README.

**Fix path:** Add `else` branch mirroring the agent registry pattern:

```python
# In librarian.py after line 1052:
else:
    content = content.strip() + f"\n\n## Global Skills\n{skill_registry_text}\n"
```

---

### GAP #3 — `copy-reports.mjs` stale path (inherited monorepo artifact)

**Severity:** LOW (dead code — not referenced by any npm script)
**Source:** `scripts/copy-reports.mjs:11`

```
  ┌─ Monorepo layout (original) ─────┐    ┌─ Standalone repo (now) ──────┐
  │                                   │    │                               │
  │  AgentFactory/                    │    │  agentfactory-webapp/         │
  │    .ai/reports/         ← 2 up    │    │    .ai/reports/    ← 1 up    │
  │    webapp/                        │    │    scripts/                  │
  │      scripts/                     │    │      copy-reports.mjs        │
  │        copy-reports.mjs           │    │        resolve("../.ai/")  ✓ │
  │          resolve("../../.ai/") ✓  │    │        resolve("../../.ai/") ✗│
  └───────────────────────────────────┘    └───────────────────────────────┘
```

**Workaround in place:** Reports are vendored as static JSON in `src/data/reports/`.
Script is not called from any npm lifecycle. No immediate action required.

---

## Workarounds Applied

The following manual steps were taken to compensate for the gaps before committing
the harness to the repo:

| Gap | Manual Workaround | Proper Fix |
|-----|------------------|------------|
| GAP #1 — missing AGENTS.md / CODEX.md / GEMINI.md | Symlinks not created; Codex/Gemini users unaffected in this webapp-only context (Claude is primary) | Fix `cli.py:260` loop |
| GAP #2 — README @skills-registry absent | `<!-- @skills-registry -->` marker not present in README; skills section missing | Fix `librarian.py:1051` else branch |
| GAP #3 — stale copy-reports.mjs path | Script already removed from all npm scripts; safe to leave as dead file | Fix path or delete script |

---

## Issues to Open in CLI Repo

| # | Title | File | Line | Priority |
|---|-------|------|------|----------|
| NEW | `init`: create root MD symlinks for ALL adapters, not just primary | `cli.py` | 260 | HIGH |
| NEW | `update_harness_files`: inject `@skills-registry` into README.md when marker absent | `librarian.py` | 1051 | MEDIUM |
| NEW | `init` output: warn when non-primary adapter root files cannot be created | `cli.py` | 267 | LOW |

---

## Conclusion

```
  ┌──────────────────────────────────────────────────────────────────┐
  │  RESULT SUMMARY                                                    │
  ├──────────────────────────────────────────────────────────────────┤
  │  Total checks     │  23                                           │
  │  Passed           │  19  ✓                                        │
  │  Failed (gaps)    │   4  ✗  (3 missing symlinks + 1 bad marker)  │
  │  Bugs found       │   1  (copy-reports.mjs path — dead code)      │
  │  Claude workaround│   0  (no harness gaps patched outside CLI)    │
  ├──────────────────────────────────────────────────────────────────┤
  │  Core harness (dirs, manifests, briefs, wiring)  →  FULLY WORKS  │
  │  Multi-adapter root symlinks                     →  PARTIAL ✗    │
  │  Registry injection in non-template README       →  PARTIAL ✗    │
  └──────────────────────────────────────────────────────────────────┘
```

The AgentFactory harness core (directory scaffolding, manifest, brief compilation,
adapter wiring, folder symlinks) works exactly as designed. The two gaps both affect
the same root cause: loops and conditionals that handle the primary adapter correctly
but fail to extend the same behaviour to secondary adapters and pre-existing files.
