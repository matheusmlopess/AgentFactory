# Feature Workflow — Standard Operating Procedure
<!-- version: 1.0.0 -->

Every feature, integration, or significant piece of new functionality follows this
lifecycle. It is enforced through skills, CI gates, and post-merge automation.
Skipping any step breaks the audit trail.

---

## Overview

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  FEATURE LIFECYCLE                                                    │
  └─────────────────────────────────────────────────────────────────────┘

  ① ISSUE          ② BRANCH         ③ IMPLEMENT      ④ GATE
  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ Create   │────►│ feature/ │────►│ Write    │────►│ CI must  │
  │ GH issue │     │ or fix/  │     │ code +   │     │ pass     │
  │ with deps│     │ branch   │     │ tests    │     │ (exit 0) │
  └──────────┘     └──────────┘     └──────────┘     └────┬─────┘
                                                           │
  ⑧ REPORT         ⑦ MILESTONE      ⑥ MERGE         ⑤ PR
  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌────▼─────┐
  │ Regen    │◄────│ Update   │◄────│ Squash   │◄────│ Open PR  │
  │ ISSUE-   │     │ milestones│    │ merge to │     │ review + │
  │ PRIORITY │     │ .md      │     │ dev      │     │ approve  │
  └──────────┘     └──────────┘     └──────────┘     └──────────┘
```

---

## Step ① — Create the GitHub Issue

Every unit of work starts as an issue. No branch without an issue.

```
  gh issue create \
    --title "feat: <summary>" \
    --label "<track-label>" \
    --body "$(cat <<'EOF'
  ## Summary
  <what and why>

  ## Acceptance Criteria
  - [ ] criterion 1
  - [ ] criterion 2

  ## References
  - Spec: docs/<SPEC>.md §N

  Depends on: #NNN  ← declare deps here so the priority report picks them up
  EOF
  )"
```

**Track labels and when to use them:**

```
  ┌─────────────────┬──────────────────────────────────────────────────┐
  │  Label          │  Use for                                          │
  ├─────────────────┼──────────────────────────────────────────────────┤
  │  enhancement    │  Harness / CLI features (no platform label)       │
  │  webapp         │  React webapp / UI work                           │
  │  cli            │  CLI command changes (with platform for SaaS)     │
  │  platform       │  SaaS platform work — add [P1]–[P4] in title     │
  │  billing        │  Stripe / monetisation (add with platform)        │
  │  registry       │  Agent registry features (add with platform)      │
  └─────────────────┴──────────────────────────────────────────────────┘
```

**★ Insight — why "Depends on" in the body matters:**
The `generate-priority-report.py` script parses every issue body for lines containing
"Depends on:" and extracts `#NNN` references. This is how the dependency graph stays
accurate without any manual matrix maintenance. Write it in the body and the BFS
wave computation picks it up automatically on the next report run.

---

## Step ② — Create a Branch

```
  git checkout dev
  git pull
  git checkout -b feature/<issue-number>-<short-slug>
```

Branch naming convention:

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  feature/<issue>-<slug>     new functionality                        │
  │  fix/<issue>-<slug>         bug fixes                                │
  │  docs/<issue>-<slug>        documentation only                       │
  │  upgrade/<artifact>-vX.Y.Z  skill or script version bump             │
  └─────────────────────────────────────────────────────────────────────┘

  Example: feature/100-skill-completeness-precommit-hook
```

---

## Step ③ — Implement

Write code, tests, and documentation. Target 80%+ test coverage for new logic.

If the feature modifies a `SKILL.md` file:

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  SKILL.md CHANGE CHECKLIST                                           │
  │                                                                       │
  │  [ ] Bump version in frontmatter (PATCH/MINOR/MAJOR)                 │
  │  [ ] Add <!-- version: X.Y.Z --> marker in title line               │
  │  [ ] Run skill completeness check before committing:                  │
  │      python3 .ai/scripts/skill-completeness-check.py --skill <name>  │
  │  [ ] Score ≥ 90% — if not, review what was lost                      │
  └─────────────────────────────────────────────────────────────────────┘
```

**★ Insight — skill files are executable specs:**
A `SKILL.md` is not documentation — it is a behavioral specification that a language
model executes. Trimming it is not like trimming a README. The completeness check
uses a second LLM call as the test oracle because only a language model can judge
semantic equivalence of LLM instructions. Score < 90% means the LLM will behave
differently after the change.

---

## Step ④ — CI Gates

Every push to a PR branch runs these jobs. All must pass before merge is allowed.

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  CI PIPELINE (.github/workflows/ci.yml)                              │
  │                                                                       │
  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
  │  │  tests           │  │  webapp-build     │  │  harness-doctor  │  │
  │  │                  │  │                  │  │                  │  │
  │  │  pytest          │  │  tsc --noEmit    │  │  exit 0  → pass  │  │
  │  │  80% coverage    │  │  vite build      │  │  exit 1  → warn  │  │
  │  │                  │  │                  │  │  exit 2  → BLOCK │  │
  │  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
  │                                                                       │
  │  ┌──────────────────────────────────────────────────────────────┐   │
  │  │  skill-completeness  (only fires when SKILL.md changes)       │   │
  │  │                                                               │   │
  │  │  score ≥ 90%  → pass    score < 90%  → BLOCK                │   │
  │  │  no API key   → skip (warning only)                          │   │
  │  └──────────────────────────────────────────────────────────────┘   │
  └─────────────────────────────────────────────────────────────────────┘
```

**Exit code semantics for harness-doctor:**

```
  exit 0  all structural checks pass              ✓ merge allowed
  exit 1  warnings (token budget, etc.)           ✓ merge allowed — review before release
  exit 2  critical: missing root, bad manifest    ✗ merge blocked
```

---

## Step ⑤ — Open a Pull Request

```
  git push -u origin feature/<issue>-<slug>

  gh pr create \
    --title "<type>: <summary> (#<issue>)" \
    --body "$(cat <<'EOF'
  ## Summary
  - <bullet: what changed>

  ## Test plan
  - [ ] <how to verify>

  Closes #<issue>
  EOF
  )"
```

---

## Step ⑥ — Merge

After approval and all CI gates green:

```
  gh pr merge <number> --merge
```

---

## Step ⑦ — Update Milestones

Immediately after merge, update `.ai/memory/milestones.md`:

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  MILESTONES UPDATE (required — never skip)                           │
  │                                                                       │
  │  1. Open .ai/memory/milestones.md                                    │
  │  2. Move issue row: Pending ──► Completed                            │
  │  3. Fill: Branch | PR# | short commit SHA | tag (if released)        │
  │  4. Bump <!-- version: X.Y.Z --> on milestones.md (PATCH)           │
  │  5. Commit:                                                           │
  │     git add .ai/memory/milestones.md                                 │
  │     git commit -m "docs: update milestones for #<issue>"             │
  └─────────────────────────────────────────────────────────────────────┘
```

**Why milestones matter:**
An issue with no Completed entry is indistinguishable from one never worked on.
The milestones file is the audit trail — it answers "what shipped and when?"
even after GitHub issues are closed.

---

## Step ⑧ — Regenerate the Priority Report

**This is the final mandatory step after every merge.**

```
  python3 .ai/scripts/generate-priority-report.py
  git add docs/ISSUE-PRIORITY.md
  git commit -m "docs: regenerate issue priority report"
```

Or it fires automatically via CI (`issue-tracker.yml`) on every push to `dev`/`main`.

**What changes in the report after a merge:**

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  BEFORE MERGE                    AFTER MERGE                         │
  │                                                                       │
  │  open-issues: 23                 open-issues: 22                     │
  │                                                                       │
  │  ⚠ Ready to Close                (section gone — issue closed)       │
  │  - #NNN implemented ...                                               │
  │                                                                       │
  │  Wave 1                          Wave 1                               │
  │  #NNN  small  ...                (issue removed)                      │
  │  ...                             ...                                   │
  │                                                                       │
  │  Wave 3                          Wave 2  ← promoted                   │
  │  #MMM  ...  (waited on #NNN)     #MMM  ...  (blocker gone)            │
  └─────────────────────────────────────────────────────────────────────┘
```

**★ Insight — why the report self-heals:**
The wave computation is a pure BFS over the live open-issue graph. Closing an issue
removes it as a node — every issue that depended on it loses a blocker and may
promote to an earlier wave. This means the "start now" list updates itself after
every merge without any manual curation. The priority matrix is never stale.

---

## Full Worked Example

A developer implements **#100 — pre-commit hook for SKILL.md completeness warning**.

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  WORKED EXAMPLE: #100                                                 │
  └─────────────────────────────────────────────────────────────────────┘

  ① Issue already exists at github.com with "Depends on:" — none
     → Wave 1 (no blockers)

  ② Branch
     git checkout -b feature/100-skill-completeness-precommit

  ③ Implement
     Create .ai/scripts/pre-commit-completeness.sh
     Write test in tests/
     chmod +x .git/hooks/pre-commit

  ④ Push → CI runs
     ┌─────────────────────────────────────────────────┐
     │  ✓  tests         (no SKILL.md changed)         │
     │  ✓  webapp-build                                │
     │  ✓  harness-doctor  exit 0                      │
     │  —  skill-completeness  (no SKILL.md change)    │
     └─────────────────────────────────────────────────┘

  ⑤ Open PR
     gh pr create --title "feat: pre-commit hook (#100)"

  ⑥ Merge
     gh pr merge 42 --merge

  ⑦ Update milestones
     #100 | feature | done | feature/100-... | #42 | abc1234 | —

  ⑧ Regen report
     python3 .ai/scripts/generate-priority-report.py
     → open-issues: 20
     → #100 gone from Wave 1
     → #101 (CI job) promoted: Wave 2 → Wave 1  ← unblocked
```

**★ Insight — the cascade effect:**
When #100 merges, #101 (the CI job) loses its only open blocker and jumps from
Wave 2 to Wave 1. If you're looking at the report right after the merge, the
next item in "Start now — no blockers" is already #101. The report answers the
question "what should I build next?" without any human curation.

---

## CI Trigger Map

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  EVENT                        WORKFLOWS TRIGGERED                    │
  ├───────────────────────────────┼─────────────────────────────────────┤
  │  push / PR (any branch)       │  ci.yml (tests, webapp, harness)    │
  │  push / PR (SKILL.md changed) │  + skill-completeness.yml           │
  │  push to dev or main          │  + issue-tracker.yml (report regen) │
  │  manual workflow_dispatch     │  issue-tracker.yml (any time)       │
  └───────────────────────────────┴─────────────────────────────────────┘
```

---

## Enforcement Checklist

Copy this into any PR description for a major feature or integration:

```
  ## Feature Workflow Checklist

  - [ ] ① Issue created with Depends on: declarations
  - [ ] ② Branch named feature/<issue>-<slug>
  - [ ] ③ Tests written (80%+ coverage for new logic)
  - [ ] ③ SKILL.md completeness check run if skill was modified
  - [ ] ④ All CI gates green
  - [ ] ⑤ PR opened — "Closes #<issue>" in body
  - [ ] ⑥ Merged
  - [ ] ⑦ milestones.md updated and committed
  - [ ] ⑧ ISSUE-PRIORITY.md regenerated (or CI auto-committed it)
```
