# Skill Completeness — System Reference
<!-- version: 2.0.0 -->

Complete reference for the AgentFactory skill completeness system: motivation,
internal mechanics, all integration points, configuration, and implementation status.

---

## 1. The Problem

A `SKILL.md` is an **executable specification for a language model** — not a library
or an API. When it is trimmed to reduce token cost, fit a smaller adapter budget, or
comply with harness size limits, there is no compile-time check that can catch a lost
branch gate, a dropped command flag, or a missing error handler.

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  THE ADAPTER-SWAP CAPABILITY DRIFT PROBLEM                            │
  │                                                                        │
  │  .ai/skills/git-versioning/SKILL.md    12,411 bytes  (full)           │
  │       │                                                                │
  │       │  agentfactory-gen adapter-add codex                           │
  │       ▼                                                                │
  │  .ai/adapters/codex/brief.md  ← skill section  ~6,000 bytes (trimmed) │
  │                                                                        │
  │  Questions the harness cannot answer without this system:             │
  │    Did the trim drop a branch-gate? A --flag? An error case?          │
  │    Will the codex agent behave the same as the claude agent?          │
  └──────────────────────────────────────────────────────────────────────┘
```

Because the subject is itself an LLM prompt, **only an LLM can be a reliable
judge of semantic equivalence**. That is the foundation of this system.

---

## 2. The Two-Phase Oracle

### 2.1 Overview

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  SKILL COMPLETENESS CHECK — INTERNAL FLOW                             │
  └──────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────┐        ┌─────────────────────────┐
  │  ORIGINAL SKILL.md       │        │  TRIMMED SKILL.md        │
  │                          │        │                          │
  │  read via:               │        │  read from:              │
  │  git show HEAD:.ai/      │        │  .ai/skills/<name>/      │
  │  skills/<name>/SKILL.md  │        │  SKILL.md (working tree) │
  └────────────┬─────────────┘        └────────────┬─────────────┘
               │                                   │
               ▼                                   │
  ╔═══════════════════════════════════╗             │
  ║  PHASE 1 — Atom Extraction        ║             │
  ║                                   ║             │
  ║  Model : claude-haiku-4-5         ║             │
  ║  Tokens: up to 4,096 output       ║             │
  ║  Cache : ephemeral on original    ║  ← cache    │
  ║                                   ║    hit on   │
  ║  Prompt: "Extract all functional  ║    re-runs  │
  ║  atoms — discrete units that      ║             │
  ║  determine LLM behavior"          ║             │
  ║                                   ║             │
  ║  Output: JSON atoms[]             ║             │
  ╚═══════════════════════════════════╝             │
               │                                   │
               │ atoms[] (JSON)                    │
               │ ← cached (ephemeral)              │
               ▼                                   ▼
  ╔══════════════════════════════════════════════════╗
  ║  PHASE 2 — Completeness Verification              ║
  ║                                                    ║
  ║  Model : claude-haiku-4-5                          ║
  ║  Tokens: up to 8,192 output                        ║
  ║  Input 1: atoms[] JSON    ← cached (ephemeral)     ║
  ║  Input 2: trimmed SKILL.md  (not cached)           ║
  ║                                                    ║
  ║  For each atom → classify:                         ║
  ║  ┌────────────────────────────────────────────┐    ║
  ║  │  preserved  full meaning intact            │    ║
  ║  │  degraded   simplified, may affect behavior│    ║
  ║  │  missing    completely absent              │    ║
  ║  └────────────────────────────────────────────┘    ║
  ╚═══════════════════════════╤════════════════════════╝
                              │
                              ▼
  ┌──────────────────────────────────────────────────────┐
  │  SCORING                                              │
  │                                                        │
  │  preserved  ×  1.0 point                              │
  │  degraded   ×  0.5 point                              │
  │  missing    ×  0.0 points                             │
  │                                                        │
  │  score = round( (Σ points / total atoms) × 100 )      │
  │  passed = score ≥ threshold                           │
  └──────────────────────────────────────────────────────┘
               │
               ▼
  .ai/reports/skill-<name>-completeness.json
```

### 2.2 Why Two Phases Instead of One

A single prompt asking "is this trimmed version complete?" produces unreliable results
because the model must simultaneously enumerate what *should* be there and notice what
is missing. Splitting the task:

- **Phase 1** anchors the ground truth in the *original* — the model can focus
  exclusively on extraction without being influenced by what is already missing.
- **Phase 2** works from an explicit, structured checklist — the model cannot
  "forget" an atom that is written in front of it.

The ephemeral cache on the original content means Phase 1 is a **cache hit** on
every re-run (e.g. iterative trimming). You only pay the full token cost once per
original version.

### 2.3 Atom Types

```
  ┌─────────────────┬────────────────────────────────────────────────────┐
  │  Atom type       │  What it captures                                   │
  ├─────────────────┼────────────────────────────────────────────────────┤
  │  decision_path  │  Routing tables, conditional branches, step-select  │
  │                 │  rules — the "if X then do Y" logic of the skill     │
  ├─────────────────┼────────────────────────────────────────────────────┤
  │  command        │  Exact shell / git / gh commands the skill tells     │
  │                 │  the LLM to run, including flags and arguments       │
  ├─────────────────┼────────────────────────────────────────────────────┤
  │  error_case     │  A specific failure condition and its required       │
  │                 │  response — "if X fails, do Y, never do Z"           │
  ├─────────────────┼────────────────────────────────────────────────────┤
  │  data_table     │  Lookup tables, color maps, status code lists,       │
  │                 │  placeholder catalogs that the LLM must reference    │
  ├─────────────────┼────────────────────────────────────────────────────┤
  │  external_ref   │  Dependencies on external files, paths, tools,       │
  │                 │  or other agents that must remain resolvable          │
  ├─────────────────┼────────────────────────────────────────────────────┤
  │  constraint     │  Explicit rules or prohibitions:                     │
  │                 │  "never skip this gate", "always use --quiet"        │
  └─────────────────┴────────────────────────────────────────────────────┘
```

### 2.4 Terminal Output (what you see when running it)

```
  $ python3 .ai/scripts/skill-completeness-check.py --skill git-versioning

  Skill Completeness Check — git-versioning
  ══════════════════════════════════════════

  ●  Phase 1 — extracting functional atoms from HEAD:git-versioning …
  ●  Extracted 45 atoms

  ●  Phase 2 — verifying 45 atoms against working tree …

  ✓  Never allow direct commits on DEFAULT_BRANCH   [constraint]
  ✓  git tag --sort=-version:refname | head -5       [command]
  ✓  PATCH / MINOR / MAJOR routing table             [decision_path]
  ✓  Rollback on failed tag push                     [error_case]
  ⚠  project-documenter delegation step              [external_ref]  — simplified
  ✓  Changelog UNRELEASED block format               [data_table]
  … (45 rows total)

  Score: 98%  ✓  PASSED (threshold 90%, adapter: claude)
  ─────────────────────────────────────────
  preserved  44    degraded  0    missing  1

  Report: .ai/reports/skill-git-versioning-completeness.json
```

---

## 3. CLI Reference

```
  python3 .ai/scripts/skill-completeness-check.py [OPTIONS]

  Required
  ─────────────────────────────────────────────────────────────────────
  --skill <name>       Skill folder name under .ai/skills/
                       e.g.  --skill diff-visualizer

  Source control
  ─────────────────────────────────────────────────────────────────────
  --old  <git-ref>     Git ref for the ORIGINAL version
                       default: HEAD  (current committed state)
  --new  <path>        Path to the TRIMMED version to verify
                       default: .ai/skills/<name>/SKILL.md (working tree)

  Output
  ─────────────────────────────────────────────────────────────────────
  --out  <path>        JSON report output path
                       default: .ai/reports/skill-<name>-completeness.json
  --quiet              Suppress terminal output (JSON still written)

  Threshold (pick one — see §5 for resolution order)
  ─────────────────────────────────────────────────────────────────────
  --adapter <name>     Adapter name → looks up threshold from
                       .ai/config/completeness.json
                       e.g.  --adapter codex  →  uses threshold 95
  --threshold <int>    Explicit override, skips config lookup entirely
                       e.g.  --threshold 95

  Exit codes
  ─────────────────────────────────────────────────────────────────────
  0   score ≥ threshold  (PASS)
  1   score <  threshold  (FAIL — skill needs review)
  2   error  (no API key, no credits, file missing, parse failure)

  Requires: ANTHROPIC_API_KEY environment variable
            anthropic Python SDK  (pip install anthropic)
```

---

## 4. JSON Report Schema

Written to `.ai/reports/skill-<name>-completeness.json`:

```jsonc
{
  "skill":        "git-versioning",
  "old_ref":      "HEAD",
  "old_version":  "1.3.0",        // extracted from SKILL.md frontmatter
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
      "description": "Never allow direct edits on DEFAULT_BRANCH",
      "status":      "preserved",
      "evidence":    "Never skip this gate. Direct commits to DEFAULT_BRANCH are wrong."
    },
    {
      "id":          "project-documenter-delegation",
      "type":        "external_ref",
      "description": "Soft delegation to project-documenter agent at Step 9",
      "status":      "missing",
      "evidence":    "Step 9 is not present in the trimmed version."
    }
  ]
}
```

---

## 5. Threshold Configuration

Thresholds live in `.ai/config/completeness.json`:

```json
{
  "completeness": {
    "thresholds": {
      "claude":  90,
      "codex":   95,
      "gemini":  90
    },
    "default": 90
  }
}
```

Codex carries a higher threshold (95%) because its tighter character budget forces
deeper trims — less room for behavioral loss is tolerated.

**Resolution order** (first match wins):

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  1. Explicit --threshold flag on the CLI                             │
  │     → overrides everything                                           │
  │                                                                       │
  │  2. --adapter <name> + matching key in completeness.json             │
  │     → e.g. --adapter codex  reads  thresholds.codex = 95            │
  │                                                                       │
  │  3. "default" key in completeness.json                               │
  │     → used when adapter is unknown or not listed                     │
  │                                                                       │
  │  4. Hardcoded fallback: 90                                           │
  │     → used when config file is absent or unreadable                  │
  └─────────────────────────────────────────────────────────────────────┘
```

---

## 6. Integration Points — Full Map

### 6.1 Where the check is called today

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  INTEGRATION MAP (all live as of v1.7.0)                              │
  └──────────────────────────────────────────────────────────────────────┘

  Developer workflow
  ──────────────────
  git commit (SKILL.md staged)
    │
    └─► .git/hooks/pre-commit
          warns + prompts "Continue? [y/N]"
          (installed from .ai/scripts/pre-commit-completeness.sh)
          bypass: SKIP_COMPLETENESS_WARN=1 git commit

  Manual health check
  ───────────────────
  bash .ai/scripts/harness-doctor.sh --completeness
    │
    └─► check_skills_completeness()
          for each skill in .ai/skills/:
            python3 .ai/scripts/skill-completeness-check.py
              --skill <name> --adapter claude --quiet
          prints ✓/⚠ per skill inline with other health checks

  Adapter swap
  ────────────
  agentfactory-gen adapter add codex
    │
    └─► step 7: _adapter_completeness_gate()
          checks each SKILL.md against codex char limit (10,000 bytes)
          warns on over-budget skills
          with --check-completeness flag:
            python3 .ai/scripts/skill-completeness-check.py
              --skill <name> --adapter codex
          with --strict flag: exits non-zero if any skill fails

  CI (on SKILL.md changes only)
  ──────────────────────────────
  .github/workflows/skill-completeness.yml
    │
    └─► matrix: [diff-visualizer, git-versioning]
          pip install anthropic
          python3 .ai/scripts/skill-completeness-check.py
            --skill <name> --adapter claude
          upload .ai/reports/*.json as artifacts
          exit 1 → blocks PR merge

  Webapp viewer (agentfactory-webapp, private repo)
  ─────────────────────────────────────────────────
  Reports in .ai/reports/*.json are consumed by the
  webapp repo. See github.com/matheusmlopess/agentfactory-webapp.
```

### 6.2 Adapter-swap gate in detail

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  agentfactory-gen adapter add <name> [--check-completeness] [--strict]│
  └──────────────────────────────────────────────────────────────────────┘
         │
         ▼  steps 1–6: create dir, config, wiring, compile brief,
         │             root symlinks, folder symlink
         │
         ▼  step 7: _adapter_completeness_gate()
         │
         ├─ read .ai/config/completeness.json
         │    → char_limit  for this adapter
         │    → threshold   for this adapter
         │
         ├─ for each .ai/skills/*/SKILL.md:
         │      size = file.stat().st_size
         │      │
         │      ├─ size ≤ char_limit
         │      │    → ✓  all skills within N byte limit for '<adapter>'
         │      │
         │      └─ size > char_limit
         │           → ⚠  warn: name, bytes, excess, CLI command
         │
         └─ if --check-completeness and over-budget skills exist:
              │
              ├─ check script exists (.ai/scripts/skill-completeness-check.py)
              ├─ check ANTHROPIC_API_KEY is set
              │
              └─ for each over-budget skill:
                   subprocess → skill-completeness-check.py
                     --skill <name> --adapter <name> --quiet
                     --out .ai/reports/skill-<name>-<adapter>-completeness.json
                   │
                   ├─ exit 0  →  ✓  <skill> passed
                   ├─ exit 1  →  ⚠  <skill> below threshold
                   └─ exit 2  →  ⚠  <skill> error: <reason>

              if --strict and any exit 1:
                raise ClickException → abort with error message
```

### 6.3 Harness-doctor integration

```
  bash .ai/scripts/harness-doctor.sh [--completeness] [--ci]

  Default run (no --completeness):
  ┌────────────────────────────────────────────────────────────────────┐
  │  ✓  Harness root present                                            │
  │  ✓  AgentFactory.md size: 4,135 bytes (limit 6,000)                │
  │  ✓  Global agent-manifest.json valid                                │
  │  ✓  milestones.md present                                           │
  │  ✓  Adapter capability symlinks present                             │
  │  ✓  Global skills total size: 13,999 bytes (limit 18,000)   ← budget│
  │  ✓  Version markers in all rules/*.md and skills/*.md               │
  └────────────────────────────────────────────────────────────────────┘

  With --completeness (requires ANTHROPIC_API_KEY):
  ┌────────────────────────────────────────────────────────────────────┐
  │  ... (all above) ...                                                │
  │  ✓  Skill completeness: diff-visualizer (100%)                      │
  │  ✓  Skill completeness: git-versioning  (98%)                       │
  └────────────────────────────────────────────────────────────────────┘

  Without API key (--completeness flag set but key missing):
  ┌────────────────────────────────────────────────────────────────────┐
  │  ... (all structural checks) ...                                    │
  │  ⚠  Skill completeness: ANTHROPIC_API_KEY not set — skipping        │
  └────────────────────────────────────────────────────────────────────┘

  Exit codes (same for both modes):
  ┌────────────────────────────────────────────────────────────────────┐
  │  0   all checks pass                                                │
  │  1   warnings present (non-blocking in CI via  || [ $? -eq 1 ])    │
  │  2   critical violations (blocks CI)                                │
  └────────────────────────────────────────────────────────────────────┘
```

### 6.4 Pre-commit hook flow

```
  git commit (with .ai/skills/**/SKILL.md staged)
         │
         ▼
  .git/hooks/pre-commit
  (installed from .ai/scripts/pre-commit-completeness.sh)
         │
         ├─ SKIP_COMPLETENESS_WARN=1 set?
         │    YES → exit 0 (bypass)
         │
         ├─ No TTY (CI environment)?
         │    YES → exit 0 (silent pass)
         │
         └─ Interactive terminal:
              ┌─────────────────────────────────────────────────────┐
              │  ⚠  SKILL.md staged for commit:                      │
              │     .ai/skills/git-versioning/SKILL.md               │
              │     → python3 .ai/scripts/skill-completeness-check.py│
              │         --skill git-versioning                        │
              │                                                       │
              │  Running the check ensures the trimmed version        │
              │  preserves all functional atoms. Score must be ≥ 90%. │
              │                                                       │
              │  Continue without running completeness check? [y/N]  │
              └─────────────────────────────────────────────────────┘
                     │              │
                    y/Y             N (or Enter)
                     │              │
                   commit        aborted
                   proceeds       → run the check, then re-commit

  Install the hook:
    cp .ai/scripts/pre-commit-completeness.sh .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit
```

### 6.5 CI workflow (skill-completeness.yml)

```
  Trigger: push or PR that touches .ai/skills/**/SKILL.md
           workflow_dispatch (manual, any skill)

  ┌─────────────────────────────────────────────────────────────────────┐
  │  Matrix: [diff-visualizer, git-versioning]  (fail-fast: false)      │
  │                                                                       │
  │  1. actions/checkout@v4  (fetch-depth: 2)                            │
  │     └─ fetch-depth: 2 needed so git show HEAD:... resolves to the    │
  │        commit *before* the current one (the pre-change original)     │
  │                                                                       │
  │  2. actions/setup-python@v5  (3.12)                                  │
  │                                                                       │
  │  3. pip install anthropic                                             │
  │                                                                       │
  │  4. python3 .ai/scripts/skill-completeness-check.py                  │
  │       --skill <matrix.skill>                                          │
  │       --adapter claude                                                │
  │     env: ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}         │
  │                                                                       │
  │  5. actions/upload-artifact@v4  (if: always())                       │
  │       name: completeness-<skill>                                      │
  │       path: .ai/reports/skill-<skill>-completeness.json              │
  └─────────────────────────────────────────────────────────────────────┘

  exit 1 (score < threshold) → job FAILS → blocks PR merge
  exit 2 (API error)         → job FAILS → investigate secret / credits
  exit 0 (passed)            → job passes → artifact uploaded

  Required GitHub secret:
    Settings → Secrets → Actions → ANTHROPIC_API_KEY
```

---

## 7. The Three Tiers

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  TIER 1 — CLI Oracle                                    LIVE          │
  │                                                                        │
  │  .ai/scripts/skill-completeness-check.py                             │
  │                                                                        │
  │  • Two-phase Claude Haiku oracle                                      │
  │  • Full atom-by-atom terminal output                                  │
  │  • JSON report written to .ai/reports/                                │
  │  • Requires ANTHROPIC_API_KEY                                         │
  │                                                                        │
  │  Called by: adapter-add, harness-doctor, CI, pre-commit hook          │
  └──────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────┐
  │  TIER 2 — Webapp Viewer                        moved → webapp-repo   │
  │                                                                        │
  │  Implemented in agentfactory-webapp (private repo).                  │
  │  Reads .ai/reports/*.json; gated behind FeatureGate plan="pro".      │
  │  See github.com/matheusmlopess/agentfactory-webapp                   │
  └──────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────┐
  │  TIER 3 — BYOK Live Checker                             PENDING (#105)│
  │                                                                        │
  │  Issue #105 — Wave 5, gated behind Pro billing (#85)                 │
  │                                                                        │
  │  • User enters Anthropic API key (stored in sessionStorage)           │
  │  • @anthropic-ai/sdk with dangerouslyAllowBrowser: true              │
  │  • "Run check" triggers two-phase oracle live in browser              │
  │  • Results replace cached report inline — no CLI needed               │
  │  • No key = cached report still visible + "Unlock Pro" prompt        │
  └──────────────────────────────────────────────────────────────────────┘
```

---

## 8. Refreshing Reports — Full Workflow

```
  SKILL.md edited (trim, restructure, or major revision)
         │
         ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │  STEP 1 — Run the oracle (requires ANTHROPIC_API_KEY)                 │
  │                                                                        │
  │  python3 .ai/scripts/skill-completeness-check.py \                   │
  │    --skill <name> --adapter <adapter>                                 │
  │                                                                        │
  │  e.g. for the claude adapter:                                         │
  │    python3 .ai/scripts/skill-completeness-check.py \                 │
  │      --skill git-versioning --adapter claude                          │
  │                                                                        │
  │  Writes: .ai/reports/skill-git-versioning-completeness.json           │
  └──────────────────────────────────────────────────────────────────────┘
         │
         ▼  score < 90%?
         │    re-trim the skill, repeat from Step 1
         │  score ≥ 90%?
         │    continue
         ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │  STEP 2 — Commit the updated SKILL.md                                 │
  │                                                                        │
  │  git add .ai/skills/<name>/SKILL.md                                  │
  │  git commit -m "feat: trim <name> SKILL.md"                          │
  │                                                                        │
  │  Pre-commit hook fires → warns → confirm or abort                    │
  └──────────────────────────────────────────────────────────────────────┘
         │
         ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │  STEP 3 — CI validates on push / PR                                   │
  │                                                                        │
  │  .github/workflows/skill-completeness.yml fires (path filter)        │
  │  Re-runs oracle in CI → blocks merge if score < threshold            │
  └──────────────────────────────────────────────────────────────────────┘
```

---

## 9. Adding a New Skill

```
  agentfactory-gen import-skill path/to/skill.zip
         │
         ▼  creates .ai/skills/<name>/SKILL.md
         │
         ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │  Generate the first report                                            │
  │                                                                        │
  │  python3 .ai/scripts/skill-completeness-check.py \                   │
  │    --skill <name> --adapter claude                                    │
  └──────────────────────────────────────────────────────────────────────┘
         │
         ▼
  Also add to CI matrix in .github/workflows/skill-completeness.yml:
    strategy:
      matrix:
        skill: [diff-visualizer, git-versioning, <name>]
```

---

## 10. Measured Results

Completeness check run on 2026-04-16 after the token-budget trim:

```
  ┌──────────────────────┬─────────┬─────────┬──────────────────────────┐
  │  Skill                │  Score  │  Atoms  │  Notes                    │
  ├──────────────────────┼─────────┼─────────┼──────────────────────────┤
  │  diff-visualizer      │  100%   │  30/30  │  All atoms preserved      │
  │  git-versioning       │   98%   │  44/45  │  1 intentional trim *     │
  └──────────────────────┴─────────┴─────────┴──────────────────────────┘

  * Missing atom: "project-documenter agent invocation (Step 9)"
    This was a soft delegation step — not a hard command or constraint.
    Intentionally removed during trim. No functional regression.
```

---

## 11. Implementation Status

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  Issue  │  Title                                        │  Status     │
  ├──────────────────────────────────────────────────────────────────────┤
  │  #100   │  Pre-commit hook for SKILL.md completeness    │  ✓ LIVE     │
  │  #101   │  Dedicated CI job (skill-completeness.yml)    │  ✓ LIVE     │
  │  #102   │  Adapter-add completeness gate                │  ✓ LIVE     │
  │  #103   │  Per-adapter thresholds in config             │  ✓ LIVE     │
  │  #104   │  Webapp static report viewer                  │  → webapp-repo │
  │  #105   │  BYOK live checker in webapp [pro]            │  → webapp-repo │
  └──────────────────────────────────────────────────────────────────────┘

  #104 and #105 have moved to the private agentfactory-webapp repo (2026-04-21).
  All CLI-side completeness track issues (#100–#103) are fully shipped as of v1.7.0.
```

---

## 12. Troubleshooting

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  Symptom                          │  Fix                              │
  ├───────────────────────────────────┼───────────────────────────────────┤
  │  Exit code 2, "no credits"        │  Add credits at                   │
  │                                   │  console.anthropic.com →          │
  │                                   │  Plans & Billing                  │
  ├───────────────────────────────────┼───────────────────────────────────┤
  │  Exit code 2, "API key not set"   │  export ANTHROPIC_API_KEY=sk-ant-…│
  ├───────────────────────────────────┼───────────────────────────────────┤
  │  git show HEAD:... failed         │  Ensure fetch-depth: 2 in CI, or  │
  │                                   │  run from inside the git repo      │
  ├───────────────────────────────────┼───────────────────────────────────┤
  │  harness-doctor skips completeness│  Pass --completeness flag and set │
  │                                   │  ANTHROPIC_API_KEY                 │
  ├───────────────────────────────────┼───────────────────────────────────┤
  │  adapter-add not showing threshold│  Check .ai/config/completeness.json│
  │  from config                      │  — adapter key must match exactly  │
  ├───────────────────────────────────┼───────────────────────────────────┤
  └──────────────────────────────────────────────────────────────────────┘
```
