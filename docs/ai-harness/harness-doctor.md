# Implement Token Budget Monitor — Live Harness Health Check

## Overview

This issue implements a **token budget monitor** that gives developers real-time visibility into context window consumption across the AI harness lifecycle. The monitor runs at key moments — session start, session end, harness switches, and git push — to surface budget violations before they silently erode context quality.

The monitor is a **zero-dependency shell script** (`harness-doctor`) that reads file sizes from disk, approximates token counts, compares against budgets in `harness.json`, and outputs a health report. No LLM calls, no external APIs, no runtime cost.

---

## Problem Statement

The tiered bootstrap protocol (from the main harness issue) defines token budgets, but budgets are useless without measurement. Today there is no mechanism to:

- Know how much context a bootstrap actually consumes
- Detect when a file silently exceeds its budget (ARCHITECTURE.md growing from 1,000 to 5,000 tokens over months)
- Warn developers before a harness switch that the target CLI will consume X% of its context window
- Catch DECISIONS.md exceeding `max_active_decisions` before it bloats the bootstrap
- Verify MANIFEST.md is in sync with actual skill directories

Without measurement, token budgets are governance theater.

---

## Design: `harness-doctor`

### Core Principle

Token estimation from file size is cheap and deterministic. The formula `tokens ≈ file_bytes / 4` (for English/code content) is accurate within ±10% for the file types in the harness (Markdown, JSON). This is good enough for budgeting — we're guarding against 2x–5x overruns, not optimizing to the last token.

### Architecture

```
harness-doctor (shell script, ~200 lines)
│
├── reads: ai/harness.json (budgets, active CLIs, handoff config)
├── reads: ai/shared/* (measures all files)
├── reads: ai/<active-cli>/* (measures CLI-specific files)
│
├── outputs: budget report to stdout (human-readable)
├── outputs: ai/.harness-health.json (machine-readable snapshot)
│
└── exit codes:
    0 = all budgets within limits
    1 = warnings (soft budget exceeded)
    2 = critical (hard ceiling exceeded or structural issues)
```

### Report Format

```
╭──────────────────────────────────────────────────────────╮
│  harness-doctor v1.0  ·  profile: claude + gemini        │
│  target CLI: claude  ·  context window: 200K tokens      │
╰──────────────────────────────────────────────────────────╯

TIER 1 — Always Loaded
  harness.json ................... 82 tok     (budget: —)
  CLAUDE.md ...................... 485 tok    (budget: —)
  CONSTRAINTS.md ................. 520 tok    (budget: 750)    ✓
  STANDARDS.md ................... 890 tok    (budget: 1,000)  ✓
  skills/MANIFEST.md ............. 280 tok    (budget: 500)    ✓
  session-state.json ............. 410 tok    (budget: 1,500)  ✓
  SESSION.md ..................... 380 tok    (budget: 1,500)  ✓
  ─────────────────────────────────────────
  Tier 1 total:                  3,047 tok   (budget: 5,000)  ✓  61%

TIER 2 — Task-Matched (worst case: all rules + all skills + decisions)
  rules/api-design.md ........... 620 tok    (budget: 750)    ✓
  rules/testing.md .............. 580 tok    (budget: 750)    ✓
  rules/security.md ............. 710 tok    (budget: 750)    ✓
  rules/performance.md .......... 430 tok    (budget: 750)    ✓
  rules/refactoring.md .......... 390 tok    (budget: 750)    ✓
  skills/security-review/
    SKILL.md + checklist.md ..... 1,240 tok  (budget: 2,000)  ✓
  skills/api-design/
    SKILL.md + checklist.md ..... 1,180 tok  (budget: 2,000)  ✓
  DECISIONS.md (24 active) ...... 3,600 tok  (budget: 4,500)  ✓  80%
  DECISIONS_INDEX.md ............ 520 tok    (budget: 1,500)  ✓
  ─────────────────────────────────────────
  Tier 2 total (worst case):     9,270 tok

TIER 3 — On Demand
  ARCHITECTURE.md ............... 1,820 tok  (budget: 1,500)  ⚠  121%
  DOMAIN.md ..................... 940 tok    (budget: 1,500)  ✓
  AGENTS.md ..................... 580 tok    (budget: 750)    ✓
  skills/security-review/
    reference.md + examples.md .. 2,800 tok  (budget: 2,000)  ⚠  140%
  DECISIONS_ARCHIVE.md .......... 4,200 tok  (not loaded unless needed)
  ─────────────────────────────────────────
  Tier 3 total (all loaded):     10,340 tok

SUMMARY
  ┌─────────────────────────────────────────────────────────┐
  │  Typical task (T1 + partial T2):    ~5,800 tok   2.9%   │
  │  Heavy task (T1 + full T2):        12,317 tok   6.2%   │
  │  Worst case (T1 + T2 + T3):       22,657 tok  11.3%   │
  │                                                         │
  │  Bootstrap target (<15,000):        ✓ typical passes    │
  │  Bootstrap ceiling (<25,000):       ✓ worst case passes │
  │  Context utilization (<12.5%):      ✓ within limits     │
  └─────────────────────────────────────────────────────────┘

WARNINGS (2)
  ⚠  ARCHITECTURE.md exceeds budget: 1,820 / 1,500 tokens (121%)
     → Refactor: split into summary + appendix, or raise budget in harness.json
  ⚠  skills/security-review/ reference.md + examples.md exceeds budget: 2,800 / 2,000 tokens (140%)
     → Refactor: trim reference.md or split into reference.md + reference-extended.md (Tier 3 only)

STRUCTURAL CHECKS
  ✓  MANIFEST.md matches skill directories (3/3)
  ✓  DECISIONS.md within rotation limit (24/30)
  ✓  session-state.json schema valid
  ✓  harness.json schema valid
  ✓  No orphaned adapter files (all match active harnesses)

Exit code: 1 (warnings present)
```

### Machine-Readable Snapshot (`ai/.harness-health.json`)

Written alongside stdout report. Used by git hooks and CI to make automated decisions.

```json
{
  "version": "1.0.0",
  "timestamp": "2025-08-15T10:32:00Z",
  "profile": "claude+gemini",
  "target_cli": "claude",
  "context_window": 200000,

  "tiers": {
    "tier1": { "tokens": 3047, "budget": 5000, "status": "ok" },
    "tier2_worst": { "tokens": 9270, "budget": null, "status": "ok" },
    "tier3_all": { "tokens": 10340, "budget": null, "status": "warning" }
  },

  "totals": {
    "typical": { "tokens": 5800, "pct": 2.9 },
    "heavy": { "tokens": 12317, "pct": 6.2 },
    "worst": { "tokens": 22657, "pct": 11.3 }
  },

  "budget_target": 15000,
  "budget_ceiling": 25000,
  "target_pass": true,
  "ceiling_pass": true,

  "warnings": [
    {
      "file": "ai/shared/ARCHITECTURE.md",
      "tokens": 1820,
      "budget": 1500,
      "pct": 121,
      "severity": "warning"
    },
    {
      "file": "ai/shared/skills/security-review/reference.md+examples.md",
      "tokens": 2800,
      "budget": 2000,
      "pct": 140,
      "severity": "warning"
    }
  ],

  "structural": {
    "manifest_sync": true,
    "decisions_within_limit": true,
    "session_state_valid": true,
    "harness_json_valid": true,
    "orphaned_adapters": false
  },

  "exit_code": 1
}
```

---

## Lifecycle Hooks

### Hook 1: Session Start — Harness Change Detection

**Trigger**: A CLI starts a session and reads `harness.json`. If `session-state.json` exists and `last_tool` differs from the current CLI, a harness change is in progress.

**Action**: The bootstrap adapter includes a directive to run `harness-doctor --target <current-cli> --quiet` before loading Tier 2. If the exit code is 2 (critical), the CLI surfaces the warnings to the user before proceeding.

**Bootstrap adapter addition:**

```markdown
## Pre-Bootstrap Health Check
Before loading Tier 2, check harness health:
- If ai/.harness-health.json exists and is <5 minutes old, read it
- If stale or missing, the user should run `harness-doctor` manually
- If any critical violations: warn the user before proceeding
- If warnings only: note them but continue
```

**Why not auto-run harness-doctor inside the CLI?** CLIs like Claude Code, Codex, and Gemini don't natively execute arbitrary scripts on session start. The adapter can only instruct the CLI to *read* the health snapshot. The script runs externally (shell alias, git hook, or manually).

**Elegant alternative — shell alias wrapper:**

```bash
# Add to .bashrc / .zshrc
claude() {
  harness-doctor --target claude --quiet 2>/dev/null
  command claude "$@"
}

codex() {
  harness-doctor --target codex --quiet 2>/dev/null
  command codex "$@"
}

gemini() {
  harness-doctor --target gemini --quiet 2>/dev/null
  command gemini "$@"
}
```

This runs the doctor automatically before every CLI invocation. The `--quiet` flag suppresses output unless there are warnings or critical issues.

### Hook 2: Session End — Budget Snapshot Update

**Trigger**: Session end is not a reliable programmatic event (the developer might just close the terminal). Instead, tie the snapshot to **file changes**.

**Approach**: Use a **filesystem watcher** or tie to git staging.

**Option A — Git pre-commit hook (recommended):**

```bash
#!/bin/sh
# .git/hooks/pre-commit

# Only run if harness files changed
if git diff --cached --name-only | grep -q "^ai/"; then
  harness-doctor --target "$(jq -r '.active_harnesses[0]' ai/harness.json)" --snapshot-only
  git add ai/.harness-health.json 2>/dev/null
fi
```

This updates the health snapshot whenever harness files are committed. Cheap (no LLM calls), automatic, and the snapshot is committed alongside the changes that caused it.

**Option B — Explicit command:**

```bash
harness-doctor --snapshot
```

Writes `ai/.harness-health.json` without terminal output. For developers who prefer manual control.

### Hook 3: Git Push — Gate on Budget Violations

**Trigger**: `git push` via a pre-push hook.

**Action**: Run `harness-doctor` and block the push if the exit code is 2 (critical budget ceiling exceeded).

```bash
#!/bin/sh
# .git/hooks/pre-push

harness-doctor --target "$(jq -r '.active_harnesses[0]' ai/harness.json)" --ci
EXIT_CODE=$?

if [ $EXIT_CODE -eq 2 ]; then
  echo ""
  echo "╭─────────────────────────────────────────────────╮"
  echo "│  ✘ PUSH BLOCKED — harness budget ceiling exceeded│"
  echo "│  Run 'harness-doctor' for details                │"
  echo "╰─────────────────────────────────────────────────╯"
  exit 1
fi

if [ $EXIT_CODE -eq 1 ]; then
  echo ""
  echo "⚠  Harness budget warnings detected. Run 'harness-doctor' for details."
  echo "   Push continuing..."
fi

exit 0
```

**Behavior:**
- Exit 0 (all clean): push proceeds silently
- Exit 1 (warnings): push proceeds with a note
- Exit 2 (critical): **push blocked** — developer must fix budgets first

### Hook 4: CI Pipeline — Budget Check as a Job

For teams using CI/CD, add `harness-doctor` as a pipeline step.

```yaml
# .github/workflows/ci.yml
harness-health:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Check harness token budgets
      run: |
        chmod +x ./ai/harness-doctor.sh
        ./ai/harness-doctor.sh --target claude --ci
    - name: Upload health report
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: harness-health
        path: ai/.harness-health.json
```

---

## Harness Switch Estimator

> When a developer is about to switch CLIs, they want to know: "How much context will the new CLI consume on bootstrap?"

### Command

```bash
harness-doctor --estimate-switch <from-cli> <to-cli>
```

### Output

```
╭──────────────────────────────────────────────────────────╮
│  Harness Switch Estimate: claude → gemini                │
╰──────────────────────────────────────────────────────────╯

                        Claude (200K)    Gemini (1M)
  ──────────────────────────────────────────────────────
  Tier 1 bootstrap:     3,047 tok        3,110 tok
  Tier 2 (typical):     2,800 tok        2,800 tok
  Total (typical):      5,847 tok        5,910 tok
  Context used:         2.9%             0.6%

  Session state ready:  ✓ session-state.json exists
  Last session tool:    claude
  Decisions pending:    24 active (within limit)
  Handoff files:        ✓ all present

  Estimated switch cost:
    Input tokens:       ~5,910  ($0.018 at Sonnet pricing)
    Output tokens:      0 (bootstrap only)

  ✓ Switch is clean — no budget violations on target CLI
```

### What It Checks

1. **Target CLI budget fit** — will the bootstrap exceed the target CLI's context budget?
2. **Session state freshness** — is `session-state.json` from the current session or stale?
3. **Decision count** — are we near the rotation threshold?
4. **Structural integrity** — all adapters present, manifest in sync?
5. **Cost estimate** — approximate dollar cost for the target CLI's bootstrap

---

## `harness-doctor` CLI Reference

```
harness-doctor [options]

Options:
  --target <cli>               Target CLI to measure (claude|codex|gemini)
                               Default: first entry in harness.json active_harnesses

  --quiet                      Suppress output unless warnings or critical issues
                               Exit codes still set correctly

  --ci                         Machine-friendly output (no colors, no box drawing)
                               Suitable for CI pipelines

  --snapshot-only              Write .harness-health.json without terminal output

  --estimate-switch <from> <to>
                               Estimate context cost for switching between CLIs

  --json                       Output full report as JSON to stdout

  --fix                        Auto-fix what can be fixed:
                               - Rotate DECISIONS.md if over limit
                               - Regenerate MANIFEST.md from skill directories
                               - Update DECISIONS_INDEX.md

  --watch                      Watch ai/ directory for changes, re-run on change
                               Useful during skill/rule authoring

  --version                    Print version and exit

Exit Codes:
  0    All budgets within limits, no structural issues
  1    Warnings present (soft budgets exceeded)
  2    Critical violations (hard ceiling exceeded or structural failures)
```

---

## The `--fix` Flag: Auto-Remediation

For common issues, `harness-doctor --fix` can auto-remediate:

| Issue | Auto-Fix Action |
|-------|----------------|
| DECISIONS.md exceeds `max_active_decisions` | Rotate oldest entries to DECISIONS_ARCHIVE.md, update DECISIONS_INDEX.md |
| MANIFEST.md missing a skill directory | Add entry to MANIFEST.md with path and placeholder triggers |
| MANIFEST.md references deleted skill | Remove stale entry from MANIFEST.md |
| Orphaned adapter (CLI removed from harness.json) | Delete adapter file |
| `.harness-health.json` stale (>24h) | Regenerate snapshot |

**What it does NOT auto-fix** (requires human judgment):
- Files exceeding token budgets (need refactoring decisions)
- session-state.json conflicts (need merge decisions)
- Missing structural files (need content authoring)

---

## Implementation Approach

### Language: Shell Script (Bash)

**Why not Node/Python?**

- Zero dependencies — runs anywhere git runs
- No install step — just `chmod +x`
- Fast — file size measurement is instant
- Portable — works in CI, local dev, containers
- The harness is about reducing complexity, not adding a build step

### Token Estimation Logic

```bash
estimate_tokens() {
  local file="$1"
  if [ ! -f "$file" ]; then
    echo 0
    return
  fi
  # bytes / 4 ≈ tokens for English/Markdown
  local bytes
  bytes=$(wc -c < "$file")
  echo $(( bytes / 4 ))
}
```

For JSON files, the ratio is closer to bytes/3.5 due to structural characters. The script can use a per-extension multiplier:

```bash
estimate_tokens() {
  local file="$1"
  local bytes
  bytes=$(wc -c < "$file")
  case "$file" in
    *.json) echo $(( bytes * 10 / 35 )) ;;  # ~bytes/3.5
    *.md)   echo $(( bytes / 4 )) ;;
    *)      echo $(( bytes / 4 )) ;;
  esac
}
```

Accuracy: ±10% for Markdown, ±15% for JSON. Good enough for budget governance (we're catching 2x–5x overruns, not ±50 tokens).

### Structural Checks

```bash
check_manifest_sync() {
  local manifest="ai/shared/skills/MANIFEST.md"
  local skill_dirs
  skill_dirs=$(find ai/shared/skills/ -mindepth 1 -maxdepth 1 -type d | sort)

  local manifest_paths
  manifest_paths=$(grep -oP 'ai/shared/skills/[a-z-]+/' "$manifest" | sort | uniq)

  diff <(echo "$skill_dirs") <(echo "$manifest_paths")
}

check_decisions_limit() {
  local max
  max=$(jq -r '.handoff.max_active_decisions // 30' ai/harness.json)
  local count
  count=$(grep -c '^## DEC-' ai/shared/DECISIONS.md 2>/dev/null || echo 0)

  if [ "$count" -gt "$max" ]; then
    echo "CRITICAL: $count decisions exceeds limit of $max"
    return 2
  fi
}
```

---

## Cost of the Monitor Itself

| Metric | Value |
|--------|-------|
| Script size | ~200 lines bash (~8 KB) |
| Runtime | <100ms (file stat operations only) |
| Dependencies | bash, jq (optional, for JSON output), wc, grep, find |
| LLM calls | **Zero** |
| Network calls | **Zero** |
| Token cost | **Zero** (runs locally, no API) |
| Disk footprint | ~8 KB script + ~2 KB health snapshot |

The monitor adds **zero runtime cost** to any CLI session. It's pure filesystem reads.

---

## Feasibility Assessment

| Aspect | Feasibility | Notes |
|--------|-------------|-------|
| Token estimation from file size | ✅ High | bytes/4 is well-established; ±10% accuracy is sufficient for budgeting |
| Shell alias wrapper for auto-run | ✅ High | Standard pattern; works in bash/zsh/fish |
| Git pre-commit hook | ✅ High | Native git feature; no tooling required |
| Git pre-push gate | ✅ High | Native git feature; can block on exit code 2 |
| CI pipeline integration | ✅ High | Just a script execution step |
| `--fix` auto-remediation | ✅ High | File operations only; decision rotation is deterministic |
| `--estimate-switch` | ✅ High | Reads both CLI configs and compares against target context window |
| `--watch` mode | ✅ Medium | Requires `inotifywait` (Linux) or `fswatch` (macOS); optional feature |
| Adapter auto-injection of health check | ⚠️ Medium | CLIs don't run scripts natively; relies on the health snapshot being fresh (shell alias solves this) |
| Cross-platform compatibility | ⚠️ Medium | Bash script works on macOS/Linux/WSL; native Windows needs Git Bash or WSL |

---

## Implementation Tasks

- [ ] Write `harness-doctor.sh` core script (~200 lines)
  - [ ] Token estimation function (per-extension multipliers)
  - [ ] Budget comparison against `harness.json`
  - [ ] Tier 1/2/3 grouping and totals
  - [ ] Structural checks (manifest sync, decision count, schema validity)
  - [ ] Color-coded terminal report
  - [ ] Exit code logic (0/1/2)
- [ ] Implement `--quiet` flag (suppress unless warnings)
- [ ] Implement `--ci` flag (no colors, no box drawing)
- [ ] Implement `--json` flag (full report as JSON)
- [ ] Implement `--snapshot-only` flag (write `.harness-health.json`)
- [ ] Implement `--estimate-switch <from> <to>` estimator
- [ ] Implement `--fix` auto-remediation
  - [ ] Decision rotation logic
  - [ ] MANIFEST.md regeneration
  - [ ] DECISIONS_INDEX.md update
  - [ ] Orphaned adapter cleanup
- [ ] Implement `--watch` mode (optional, requires fswatch/inotifywait)
- [ ] Create `.git/hooks/pre-commit` template
- [ ] Create `.git/hooks/pre-push` template
- [ ] Create shell alias examples (bash/zsh/fish)
- [ ] Create GitHub Actions workflow template
- [ ] Write README section for harness-doctor
- [ ] Test: fresh single-CLI project (all clean, exit 0)
- [ ] Test: mature project with budget warnings (exit 1)
- [ ] Test: project with ceiling violation (exit 2)
- [ ] Test: `--fix` decision rotation at threshold
- [ ] Test: `--fix` manifest regeneration
- [ ] Test: `--estimate-switch` for all CLI pairs
- [ ] Test: pre-push hook blocks on exit 2, passes on 0 and 1

---

## Acceptance Criteria

- [ ] `harness-doctor` runs in <100ms on a typical project
- [ ] Token estimates are within ±15% of actual tokenizer output (validate against `tiktoken` or Anthropic tokenizer for a sample of files)
- [ ] Exit codes are correct: 0 (clean), 1 (warnings), 2 (critical)
- [ ] `--fix` correctly rotates decisions and regenerates MANIFEST
- [ ] `--estimate-switch` accurately reports context % for target CLI
- [ ] Pre-commit hook updates `.harness-health.json` only when `ai/` files change
- [ ] Pre-push hook blocks push only on exit code 2
- [ ] Shell alias wrapper runs doctor before CLI invocation without noticeable delay
- [ ] CI workflow template works in GitHub Actions
- [ ] Script has zero external dependencies beyond bash, standard coreutils, and optionally jq
- [ ] Works on macOS, Linux, and WSL

---

## Relationship to Main Harness Issue

This issue is a **companion feature** to the main harness issue. It implements the budget governance that the main issue defines but cannot enforce without tooling.

| Main Harness Issue | This Issue |
|-------------------|------------|
| Defines token budgets in harness.json | Measures actual token counts against budgets |
| Defines tiered bootstrap protocol | Reports per-tier consumption |
| Defines decision rotation rules | Implements auto-rotation via `--fix` |
| Defines MANIFEST.md for skill discovery | Validates manifest sync via structural checks |
| Defines scaling guides (add/remove CLI) | Provides `--estimate-switch` for safe transitions |

Without this issue, the budgets in harness.json are aspirational. With it, they're enforced.
