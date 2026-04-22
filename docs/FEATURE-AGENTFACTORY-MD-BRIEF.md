# AgentFactory.md — Master Brief & Project Context Injection
<!-- version: 1.0.0 -->

Issue: #125 · Every adapter brief now carries project context; AgentFactory.md compiled as full master brief

---

## 1. Problem Statement

FormatSwitch (#96) was a major step forward: it gave each CLI a compiled brief in its
own format. But it introduced a silent regression. Before FormatSwitch, all root files
(`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`) were symlinks to `.ai/AgentFactory.md` — the
developer's source of truth. After FormatSwitch they pointed to adapter-specific
compiled briefs that had skills, rules, and agents, but **zero project context**.

```
  ┌────────────────────────────────────────────────────────────────────────┐
  │  THE GAP                                                                │
  │                                                                         │
  │  Developer starts on Claude. Claude reads a brief with architecture,   │
  │  dev commands, and project overview.                                   │
  │                                                                         │
  │  Developer switches to Codex mid-project.                              │
  │  Codex reads AGENTS.md — skills ✓, rules ✓, agents ✓                  │
  │                         — architecture ✗, dev commands ✗, overview ✗  │
  │                                                                         │
  │  The agent is context-blind. It will ask questions, make wrong         │
  │  assumptions, and produce work that doesn't fit the project.           │
  └────────────────────────────────────────────────────────────────────────┘
```

At the same time, `.ai/AgentFactory.md` itself was never compiled — it received
`@agent-registry` and `@skills-registry` injections from `update_harness_files()`,
but never got the rules or commands sections that every adapter brief had. A developer
reading it directly would miss half the compiled context.

---

## 2. Solution Overview

Three changes shipped together:

| Phase | What | Why |
|-------|------|-----|
| 1 | Extract preamble from `AgentFactory.md` and inject it as `## Project Context` into every adapter brief, budget-fitted to each adapter's character limit | Every CLI gets project context on CLI swap without any manual step |
| 2 | Compile `AgentFactory.md` as a full master brief — upsert `@commands` + `@rules` sections | AgentFactory.md is now as rich as any adapter brief; single place to read everything |
| 3 | List `.ai/AgentFactory.md` explicitly in the Harness Identity Block shared-context section | Any agent following the identity block navigation now finds the master document |

---

## 3. Complete Workflow

```
╔══════════════════════════════════════════════════════════════════════════════╗
║              AgentFactory — Complete Development Workflow                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ① Harness Layout  ·  ② Compilation Pipeline  ·  ③ Brief Anatomy           ║
║  ④ CLI Switch Scenario  ·  ⑤ Development Loop                               ║
╚══════════════════════════════════════════════════════════════════════════════╝


┌─── ① HARNESS LAYOUT (.ai/) ────────────────────────────────────────────────┐
│                                                                              │
│  .ai/                                                                        │
│  ├── AgentFactory.md      ← master brief                                    │
│  │     preamble (human-written)                                              │
│  │     <!-- @agent-registry -->      auto-managed by update_harness_files   │
│  │     <!-- @skills-registry -->     auto-managed by update_harness_files   │
│  │     <!-- @commands-start/end -->  compiled by agentfactory-gen ← NEW     │
│  │     <!-- @rules-start/end -->     compiled by agentfactory-gen ← NEW     │
│  ├── agent-manifest.json  ← global agent registry                           │
│  ├── adapters/                                                               │
│  │   ├── claude/                                                             │
│  │   │   ├── brief.md  ←── CLAUDE.md (root symlink)                         │
│  │   │   ├── skills/   ──► ../../skills                                     │
│  │   │   └── commands/ ──► ../../commands                                   │
│  │   ├── codex/                                                              │
│  │   │   ├── brief.md  ←── AGENTS.md · CODEX.md (root symlinks)             │
│  │   │   ├── skills/   ──► ../../skills                                     │
│  │   │   └── prompts/  ──► ../../commands                                   │
│  │   └── gemini/                                                             │
│  │       ├── brief.md  ←── GEMINI.md (root symlink)                         │
│  │       └── tools/    ──► ../../skills                                     │
│  ├── skills/    SKILL.md + skill-manifest.json per skill                    │
│  ├── rules/     *.md behavior constraints                                   │
│  ├── commands/  *.md slash-commands / prompt templates                      │
│  ├── agents/    deployed agent dirs (5-dir standard)                        │
│  └── memory/                                                                 │
│      └── milestones.md  ← single source of truth for issues                 │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘


┌─── ② COMPILATION PIPELINE  (agentfactory-gen brief) ───────────────────────┐
│                                                                              │
│  Input sources                          _compile_adapter_briefs()           │
│  ─────────────────────                  ──────────────────────────          │
│                                                                              │
│  .ai/skills/         ──┐                                                     │
│  .ai/agents/         ──┤──► data = { skills, agents, commands, rules,       │
│  .ai/commands/       ──┤             project_context }  ← NEW               │
│  .ai/rules/          ──┤                    │                                │
│  AgentFactory.md     ──┘  (preamble only)   │  _render_brief() per adapter  │
│        ▲                                    │                                │
│        │ also WRITTEN back                  └──────┬──────────┬─────────┐   │
│        │ _compile_agentfactory_md() ← NEW          ▼          ▼         ▼   │
│        │ upserts @commands + @rules           ┌────────┐ ┌────────┐ ┌──────┐│
│        └──────────────────────────────────────│ claude │ │ codex  │ │gemini││
│                                               │ 4000 ch│ │ 2000 ch│ │4000ch││
│                                               │brief.md│ │brief.md│ │brief ││
│                                               └────────┘ └────────┘ └──────┘│
└──────────────────────────────────────────────────────────────────────────────┘


┌─── ③ BRIEF ANATOMY (per adapter) ──────────────────────────────────────────┐
│                                                                              │
│  AgentFactory.md                      Compiled adapter brief                │
│  ┌───────────────────────────┐        ┌─────────────────────────────────┐   │
│  │ # AgentFactory            │        │ # Intelligence Brief — <CLI>    │   │
│  │ Overview, architecture,   │──┐     │ <!-- @compiled-by: af-gen -->   │   │
│  │ dev commands, notes…      │  │     ├─────────────────────────────────┤   │
│  │  ← preamble (extracted)   │  │     │ ## Harness                      │   │
│  ├───────────────────────────┤  │     │   .ai/AgentFactory.md  ← ref    │   │
│  │ <!-- @agent-registry -->  │  │     │   nav block + all adapter links │   │
│  │ <!-- @skills-registry --> │  │     ├─────────────────────────────────┤   │
│  ├───────────────────────────┤  └────►│ ## Project Context  ← NEW       │   │
│  │ <!-- @commands-start -->  │        │   budget-fit preamble injected  │   │
│  │  …commands…   ← compiled  │        │   claude · gemini : ≤ 4000 ch   │   │
│  │ <!-- @commands-end -->    │        │   codex           : ≤ 2000 ch   │   │
│  ├───────────────────────────┤        │   (truncated → ⚠ html comment) │   │
│  │ <!-- @rules-start -->     │        ├─────────────────────────────────┤   │
│  │  …rules…      ← compiled  │        │ ## Available Skills             │   │
│  │ <!-- @rules-end -->       │        │ ## Registered Agents            │   │
│  └───────────────────────────┘        │ ## Behavior Rules               │   │
│                                       └─────────────────────────────────┘   │
│                                                                              │
│  _collect_project_context()  → strips H1 title, stops at first <!-- @       │
│  _fit_context_to_budget()    → truncates at paragraph boundary if over limit│
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘


┌─── ④ CLI SWITCH SCENARIO ──────────────────────────────────────────────────┐
│                                                                              │
│  Developer switches Claude → Codex mid-project                              │
│                                                                              │
│  ✗ BEFORE (#96 FormatSwitch gap)         ✓ AFTER (this PR, #125)            │
│  ┌──────────────────────────────┐        ┌──────────────────────────────┐   │
│  │ AGENTS.md → codex/brief.md  │        │ AGENTS.md → codex/brief.md  │   │
│  │ ─────────────────────────── │        │ ─────────────────────────── │   │
│  │ ## Harness (nav only)    ✓  │        │ ## Harness (nav + AF.md) ✓  │   │
│  │ ## Available Skills      ✓  │        │ ## Project Context  ← NEW   │   │
│  │ ## Registered Agents     ✓  │        │    arch + cmds (2000 ch max)│   │
│  │ ## Behavior Rules        ✓  │        │    ⚠ if truncated: warned   │   │
│  │                              │        │ ## Available Skills      ✓  │   │
│  │ ✗ no architecture overview   │        │ ## Registered Agents     ✓  │   │
│  │ ✗ no dev commands            │        │ ## Behavior Rules        ✓  │   │
│  │ ✗ no project context         │        └──────────────────────────────┘   │
│  └──────────────────────────────┘                                            │
│                                                                              │
│  Run after switch:  agentfactory-gen brief                                  │
│                     → all briefs recompiled with current preamble           │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘


┌─── ⑤ DEVELOPMENT LOOP ─────────────────────────────────────────────────────┐
│                                                                              │
│   ┌──────────────┐    ┌────────────────────────┐    ┌──────────────────┐   │
│   │  GitHub      │    │  feature branch         │    │  implement       │   │
│   │  issue       ├───►│  git checkout -b        ├───►│  edit code       │   │
│   │  opened      │    │  feature/<name>         │    │  add tests       │   │
│   └──────────────┘    └────────────────────────┘    └────────┬─────────┘   │
│                                                               │              │
│                                                               ▼              │
│                                              ┌────────────────────────────┐ │
│                                              │  pytest src/tests/ -q      │ │
│                                              │  ruff check .              │ │
│                                              │  203+ tests green ✓        │ │
│                                              └──────────────┬─────────────┘ │
│                                                             │                │
│   ┌────────────────────────────┐    ┌──────────────┐       │                │
│   │  agentfactory-gen brief    │    │  merge PR    │       │                │
│   │  milestones.md update      │◄───│  → dev       │◄─── gh pr create      │
│   │  CHANGELOG version bump    │    └──────────────┘                        │
│   └────────────────────────────┘                                            │
│                                                                              │
│  Key rules:                                                                  │
│  · Every task → feature branch  (never commit directly to dev)              │
│  · Every .md  → version marker  (<!-- version: x.y.z -->)                  │
│  · Every new logic → ≥ 80% test coverage                                   │
│  · Secrets never logged, printed, or committed                              │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Gap Analysis (found during design)

The diagram work that produced this feature exposed six architectural gaps:

### G1 — WORKFLOWS.md diagram 1 was architecturally stale
The Mermaid overall-architecture diagram showed `CLAUDE.md →|symlink| AgentFactory.md`.
This was true before FormatSwitch (#96). After it, root files point to compiled adapter
briefs (`adapters/claude/brief.md`). The diagram was never updated. **Fixed in this PR.**

### G2 — AgentFactory.md described as "legacy + sync target" in README
After this PR it is the primary master brief — compiled with full rules and commands
sections on every `agentfactory-gen brief` run. The "legacy" label was misleading.
**Fixed in this PR.**

### G3 — No project context survived a CLI swap
The FormatSwitch compilation collected skills/agents/commands/rules but never read
the preamble of `AgentFactory.md`. A Codex or Gemini agent opening a Claude project
had zero project context: no architecture, no dev commands, no overview.
**Fixed in this PR (Phase 1 — preamble injection).**

### G4 — AgentFactory.md itself had no compiled sections
Rules, commands, and skills were compiled into per-adapter briefs but never back
into `AgentFactory.md`. The "master doc" was therefore less complete than the briefs
it fed. **Fixed in this PR (Phase 2 — `_compile_agentfactory_md`).**

### G5 — Harness Identity Block omitted AgentFactory.md from shared-context list
The navigation section in every brief listed `skills/`, `rules/`, `agent-manifest.json`
and `memory/milestones.md` — but not `AgentFactory.md`, the most important file to read
after a CLI swap. **Fixed in this PR (`_fmt_harness_identity`).**

### G6 — No per-adapter context budget (open until this PR)
`_FORMAT_REGISTRY` had `skill_char_limit` per adapter, but no concept of a budget for
project-context injection. Without it, all adapters would get the same preamble
regardless of their effective context windows. **Fixed: `context_char_limit` added.**

---

## 5. Technical Reference

### 5.1 Per-adapter context limits

| Adapter | `context_char_limit` | Reason |
|---------|---------------------|--------|
| `claude` | 4 000 chars | Large context window; full preamble fits |
| `codex` | 2 000 chars | Tighter instruction-following window; prioritise reliability |
| `gemini` | 4 000 chars | Large context window; full preamble fits |

### 5.2 Preamble extraction (`_collect_project_context`)

```python
# src/agent_gen/librarian.py

def _collect_project_context(project_root: str) -> str:
    af_path = Path(project_root) / HARNESS_ROOT / CONTEXT_FILE
    content = af_path.read_text(encoding="utf-8")
    marker = content.find("<!-- @")               # stop before first registry block
    preamble = content[:marker].strip()
    lines = preamble.splitlines()
    if lines and lines[0].startswith("# "):       # strip H1 title (duplicates header)
        lines = lines[1:]
    return "\n".join(lines).strip()
```

### 5.3 Budget fitting (`_fit_context_to_budget`)

Truncation happens at the last `\n\n` paragraph break before the limit. If no break
is found in the first half of the window, the hard limit is used. The truncation is
always annotated with an HTML comment so the AI agent can see exactly what was cut:

```
<!-- ⚠ context truncated: 3276 → 2000 chars for 95% budget. -->
```

When `AGENTFACTORY_LICENSE_KEY` is set, the comment also includes a completeness-check
hint (advisory only, non-blocking). Full semantic oracle support tracked in #126.

### 5.4 AgentFactory.md compilation (`_compile_agentfactory_md`)

Called at the end of every `_compile_adapter_briefs()` run. Uses Claude's formatters
(`_fmt_commands_list`, `_fmt_rules_list`) to produce the most readable universal
markdown. Marker blocks are appended if absent, replaced in-place if already present.

```
<!-- @commands-start -->
## Commands
- `/completeness-check` — ...
- `/git-workflow` — ...
<!-- @commands-end -->

<!-- @rules-start -->
## Behavior Rules
- **Quiet Mode:** ...
- **Branches:** ...
<!-- @rules-end -->
```

---

## 6. CLI Switch Walkthrough

Full step-by-step for a developer switching from Claude to Codex:

```
1.  Open project in Codex CLI.
    Codex reads AGENTS.md → compiled codex/brief.md.

2.  Brief now contains:
    ## Harness
      .ai/AgentFactory.md  ← project overview + master compiled brief  ← NEW
      .ai/skills/  .ai/rules/  .ai/agent-manifest.json  .ai/memory/milestones.md
      claude  CLAUDE.md  → .ai/adapters/claude/brief.md
      codex   AGENTS.md  → .ai/adapters/codex/brief.md   ← YOU ARE HERE
      gemini  GEMINI.md  → .ai/adapters/gemini/brief.md

    ## Project Context                                                   ← NEW
      [project architecture, dev commands, overview — up to 2000 chars]
      <!-- ⚠ context truncated: 3276 → 2000 chars --> (if preamble > 2000)

    ## Available Skills  ...
    ## Registered Agents ...
    ## Behavior Rules    ...

3.  If codex adapter was not yet activated:
    agentfactory-gen adapter add codex

4.  If briefs are stale after pulling new code:
    agentfactory-gen brief
    → recompiles all active adapter briefs with current preamble
```

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `## Project Context` missing from brief | Brief compiled before #125 | `agentfactory-gen brief` |
| `context truncated` warning in codex brief | Preamble > 2000 chars (normal) | Shorten `AgentFactory.md` preamble, or accept truncation |
| AgentFactory.md missing `@commands-start` | Brief never compiled after #125 | `agentfactory-gen brief` |
| `## Project Context` shows registry blocks | `AgentFactory.md` has preamble after the `<!-- @` marker | Move human text above the first `<!-- @` marker |

---

## 8. Open Ends

| Issue | Title | Status |
|-------|-------|--------|
| #126 | feat: extend completeness oracle to project-context preamble truncation | pending |

When `AGENTFACTORY_LICENSE_KEY` is set and the preamble is truncated, the system
currently adds a hint comment but does not run the oracle. #126 tracks extending the
two-phase semantic completeness check to measure information loss during truncation
and surface a completeness delta (e.g. `⚠ preamble completeness: 74%`).
