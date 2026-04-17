# Skill Completeness — Design Spec & Study
<!-- version: 1.0.0 -->

This document specifies the Skill Completeness system: its motivation, internal logic,
workflow integration points, and the adapter-swap capability-preservation problem it
solves. It is intended as a study reference and a roadmap for future implementation
issues.

---

## 1. The Problem

A `SKILL.md` file is an **executable specification for a language model**. When it is
trimmed — to reduce token cost, to fit a smaller adapter budget, or to comply with
harness size limits — there is no automated way to know whether the trimmed version
still produces the same LLM behavior.

This is compounded by the **adapter-swap problem**: a project that starts on Claude
and migrates to Codex must recompile its briefs to fit Codex's smaller character limits.
The same skill may need to be trimmed by 40–60%. Without a gate, capability silently
degrades across the adapter boundary.

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  THE ADAPTER-SWAP CAPABILITY DRIFT PROBLEM                       │
  │                                                                   │
  │  claude/brief/git-versioning.md     12 411 bytes  (full)         │
  │       │                                                           │
  │       │  adapter-add codex                                        │
  │       ▼                                                           │
  │  codex/brief/git-versioning.md       6 000 bytes  (trimmed)      │
  │                                                                   │
  │  Question: did the trim drop a branch gate? a command flag?       │
  │            an error case? No test exists to answer this.          │
  └─────────────────────────────────────────────────────────────────┘
```

---

## 2. Solution: Two-Phase LLM Oracle

The skill completeness checker uses a second LLM call (Claude Haiku) as a test oracle.
Because the subject is itself an LLM prompt file, a language model is the only reliable
judge of semantic equivalence.

### 2.1 High-Level Flow

```
  ┌─────────────────────────────────────────────────────────────────┐
  │              SKILL COMPLETENESS CHECK — FULL FLOW                │
  └─────────────────────────────────────────────────────────────────┘

  INPUTS
  ┌──────────────────┐          ┌──────────────────┐
  │  ORIGINAL         │          │  TRIMMED          │
  │  SKILL.md         │          │  SKILL.md         │
  │  (git ref / path) │          │  (working tree)   │
  └────────┬─────────┘          └────────┬──────────┘
           │                             │
           ▼                             │
  ╔════════════════════════════╗         │
  ║  PHASE 1 — Atom Extraction ║         │
  ║                            ║         │
  ║  Model : claude-haiku-4-5  ║         │
  ║  Tokens: up to 4 096       ║         │
  ║  Cache : ephemeral on      ║         │
  ║          original content  ║         │
  ║                            ║         │
  ║  Extracts all "functional  ║         │
  ║  atoms" — discrete units   ║         │
  ║  of LLM behavior           ║         │
  ╚══════════════╤═════════════╝         │
                 │ atoms[]               │
                 ▼                       ▼
  ╔══════════════════════════════════════════╗
  ║  PHASE 2 — Completeness Verification     ║
  ║                                          ║
  ║  Model : claude-haiku-4-5                ║
  ║  Tokens: up to 8 192                     ║
  ║  Cache : atoms[] (ephemeral)             ║
  ║                                          ║
  ║  For each atom → classify status:        ║
  ║  ┌──────────────────────────────────┐    ║
  ║  │  preserved  full meaning intact  │    ║
  ║  │  degraded   simplified, may vary │    ║
  ║  │  missing    completely absent    │    ║
  ║  └──────────────────────────────────┘    ║
  ╚══════════════════╤═══════════════════════╝
                     │
                     ▼
  ┌──────────────────────────────────────────┐
  │  SCORING                                  │
  │                                           │
  │  preserved  ×  1.0 pt                     │
  │  degraded   ×  0.5 pt                     │
  │  missing    ×  0.0 pt                     │
  │                                           │
  │  score = round( Σpts / total × 100 )      │
  │  passed = score ≥ threshold (default 90)  │
  └──────────────────────────────────────────┘

  OUTPUT: .ai/reports/skill-<name>-completeness.json
```

### 2.2 Atom Types

A "functional atom" is one discrete unit of LLM behavioral specification:

```
  ┌────────────────┬───────────────────────────────────────────────┐
  │  Atom Type     │  Description                                   │
  ├────────────────┼───────────────────────────────────────────────┤
  │ decision_path  │ routing tables, conditionals, step selection   │
  │ command        │ exact shell / git / gh commands                │
  │ error_case     │ specific failure condition + required response  │
  │ data_table     │ lookup tables, color maps, placeholder lists   │
  │ external_ref   │ dependencies on files, tools, other agents     │
  │ constraint     │ explicit rules: "never skip", "always use X"   │
  └────────────────┴───────────────────────────────────────────────┘
```

### 2.3 JSON Report Schema

```json
{
  "skill":        "git-versioning",
  "old_ref":      "HEAD",
  "old_version":  "1.3.0",
  "new_version":  "1.3.1",
  "generated_at": "2026-04-16T11:16:56Z",
  "score":        98,
  "threshold":    90,
  "passed":       true,
  "summary": {
    "preserved": 44,
    "degraded":   0,
    "missing":    1
  },
  "atoms": [
    {
      "id":          "session-branch-gate",
      "type":        "constraint",
      "description": "Never allow edits directly on DEFAULT_BRANCH",
      "status":      "preserved",
      "evidence":    "Never skip this gate. Direct commits to DEFAULT_BRANCH are always wrong."
    }
  ]
}
```

---

## 3. CLI Reference

```
python3 .ai/scripts/skill-completeness-check.py [OPTIONS]

  --skill     <name>    Skill folder under .ai/skills/           (required)
  --old       <ref>     Git ref for original       (default: HEAD)
  --new       <path>    Path to trimmed version    (default: .ai/skills/<name>/SKILL.md)
  --out       <path>    JSON report output path    (default: .ai/reports/skill-<name>-completeness.json)
  --threshold <int>     Min % to pass              (default: 90)
  --quiet               Suppress terminal output

Exit codes
  0   score ≥ threshold
  1   score < threshold
  2   error (no API key, no credits, parse failure)

Requires: ANTHROPIC_API_KEY environment variable
```

---

## 4. Current Harness Integration

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  HARNESS-DOCTOR INTEGRATION (existing)                           │
  └─────────────────────────────────────────────────────────────────┘

  bash .ai/scripts/harness-doctor.sh [--completeness]

  Without --completeness (default / --ci):
  ┌──────────────────────────────────────────┐
  │  ✓  Harness root present                  │
  │  ✓  AgentFactory.md size: 4135 bytes      │
  │  ✓  Global agent-manifest.json valid      │
  │  ✓  milestones.md present                 │
  │  ✓  Adapter capability symlinks present   │
  │  ✓  Global skills total size: 13 999 bytes│  ← budget gate
  │  ✓  Version markers present               │
  └──────────────────────────────────────────┘

  With --completeness (optional, requires API key):
  ┌──────────────────────────────────────────┐
  │  ... (all above) ...                      │
  │  ✓  Skill completeness: diff-visualizer   │  (100%)
  │  ✓  Skill completeness: git-versioning    │  (98%)
  └──────────────────────────────────────────┘

  Exit codes:
    0  all pass
    1  warnings (non-blocking in CI — see .github/workflows/ci.yml)
    2  critical violations
```

---

## 5. Proposed: Adapter-Swap Gate

This is the primary unimplemented integration point. When compiling briefs for a new
adapter, the completeness check should run automatically to confirm the trimmed brief
preserves the original's capability.

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  PROPOSED ADAPTER-SWAP WORKFLOW                                   │
  └─────────────────────────────────────────────────────────────────┘

  agentfactory-gen adapter-add codex
           │
           ▼
  ┌────────────────────────────────────┐
  │  For each skill in agent manifest  │
  └──────────────┬─────────────────────┘
                 │
         ┌───────┴────────┐
         │                │
    size ≤ limit?    size > limit?
         │                │
         ▼                ▼
    copy as-is       trim to fit
         │           codex budget
         │                │
         └───────┬─────────┘
                 │
                 ▼
  ╔════════════════════════════════════╗
  ║  COMPLETENESS GATE  (new step)     ║
  ║                                    ║
  ║  original = claude/brief/<skill>   ║
  ║  trimmed  = codex/brief/<skill>    ║
  ║  threshold = per-adapter config    ║
  ║                                    ║
  ║  score ≥ threshold?                ║
  ║    YES ──► brief accepted          ║
  ║    NO  ──► warn / block deploy     ║
  ╚════════════════════════════════════╝
```

Per-adapter thresholds are appropriate because smaller budgets demand higher precision:

```
  ┌────────────────┬───────────────┬─────────────────────────────────┐
  │  Adapter       │  Threshold    │  Rationale                       │
  ├────────────────┼───────────────┼─────────────────────────────────┤
  │  claude        │  90%          │  large budget, some loss OK      │
  │  codex         │  95%          │  tight budget, less tolerance    │
  │  gemini        │  90%          │  similar budget to claude        │
  └────────────────┴───────────────┴─────────────────────────────────┘
```

---

## 6. Proposed: Pre-Commit Hook

Warns when a `SKILL.md` file is staged for commit without running the completeness
check. Non-blocking in terminal, can be bypassed with `SKIP_COMPLETENESS_WARN=1`.

```
  git commit (with SKILL.md staged)
          │
          ▼
  ┌───────────────────────────────────────┐
  │  .git/hooks/pre-commit                │
  │                                       │
  │  SKILL.md detected in staged files?   │
  │    NO  ──► proceed normally           │
  │    YES ──► show warning               │
  │            prompt: Continue? [y/N]    │
  │            y ──► commit proceeds      │
  │            N ──► commit aborted       │
  └───────────────────────────────────────┘
```

---

## 7. Proposed: Dedicated CI Job

A separate workflow that fires only when `SKILL.md` files change, distinct from the
main `harness-doctor` CI run.

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  .github/workflows/skill-completeness.yml                        │
  └─────────────────────────────────────────────────────────────────┘

  Triggers
  ┌──────────────────────────────────────────────────────────────┐
  │  push / PR    paths: .ai/skills/**/SKILL.md                  │
  │  workflow_dispatch  (manual, any skill)                       │
  └──────────────────────────────────────────────────────────────┘

  Matrix: [ diff-visualizer, git-versioning ]  (one job per skill)

  Steps
  ┌──────────────────────────────────────────────────────────────┐
  │  1. checkout  (fetch-depth: 2 for git show HEAD to resolve)  │
  │  2. setup-python 3.12                                        │
  │  3. pip install anthropic                                    │
  │  4. run skill-completeness-check.py --threshold 90           │
  │  5. upload report JSON as artifact                           │
  └──────────────────────────────────────────────────────────────┘

  Requires: ANTHROPIC_API_KEY GitHub secret
  Exit 1 (below threshold) ──► job fails, blocks PR merge
```

---

## 8. Proposed: Webapp Integration

Three options in increasing implementation cost:

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  OPTION A — Report Viewer (no API calls)    LOW COST            │
  │                                                                   │
  │  • Embed pre-generated JSON reports as static TS imports          │
  │  • Render score + atom breakdown in UI                            │
  │  • "Re-run" shows CLI command to copy-paste                       │
  │  • No @anthropic-ai/sdk needed                                    │
  └─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │  OPTION B — CI Artifact Link                ZERO COST           │
  │                                                                   │
  │  • Webapp links to latest CI artifact                             │
  │  • "Run check" button = GitHub workflow_dispatch API call         │
  │  • Always shows latest committed-state result                     │
  │  • No browser API key management                                  │
  └─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │  OPTION C — BYOK Live Check                 HIGH COST           │
  │                                                                   │
  │  • User enters Anthropic API key (sessionStorage)                 │
  │  • Two-phase API call runs in browser                             │
  │  • dangerouslyAllowBrowser: true on SDK                          │
  │  • Full atom-by-atom results rendered inline                      │
  │  • Paid gate: no key = locked (cached reports still visible)      │
  └─────────────────────────────────────────────────────────────────┘
```

**Recommendation:** Ship Option A first (no dependencies), then Option B alongside
the CI job (issue #B below), defer Option C to the Pro tier milestone.

---

## 9. Measured Results (Current State)

Completeness check was run on 2026-04-16 after the token-budget trim
(`fix/harness-doctor-skill-budget` branch):

```
  ┌──────────────────────────────────────────────────────┐
  │  Skill              │  Score  │  Atoms  │  Missing    │
  ├──────────────────────────────────────────────────────┤
  │  diff-visualizer    │  100%   │  30/30  │  0          │
  │  git-versioning     │   98%   │  44/45  │  1 *        │
  └──────────────────────────────────────────────────────┘

  * Missing atom: "project-documenter agent invocation (Step 9)"
    This was an intentional trim — a soft delegation step, not a hard command.
    No functional regressions detected.
```

---

## 10. Implementation Issues

See GitHub for the breakdown:

| Issue | Title |
|-------|-------|
| #A | `feat: pre-commit hook for SKILL.md completeness warning` |
| #B | `feat: skill-completeness CI job (skill-completeness.yml)` |
| #C | `feat: integrate completeness gate into adapter-add command` |
| #D | `feat: per-adapter completeness thresholds in harness config` |
| #E | `feat: webapp report viewer for completeness JSON (Option A)` |
| #F | `feat[pro]: BYOK live completeness checker in webapp (Option C)` |

Issues are ordered by dependency: A → B → C → D → E → F.
