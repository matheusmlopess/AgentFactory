# HOWTO: Skill Completeness Check
<!-- version: 1.1.0 -->

The skill completeness oracle verifies that a trimmed `SKILL.md` preserves all
functional behaviour of the original. It uses a two-phase Claude Haiku pipeline to
extract **functional atoms** (commands, decision paths, error cases, constraints, etc.)
from the original, then verifies each atom is present in the trimmed version.

The oracle now supports three modes, agent-level checking, and model selection.
Some flags require a Pro plan — these are marked `[pro]` in the reference below.

---

## Quick Reference

```
python3 .ai/scripts/skill-completeness-check.py [options]

Target (one required):
  --skill <name>         Global skill: .ai/skills/<name>/SKILL.md
  --agent <name>         Agent: all SKILL.md under .ai/agents/<name>/skills/  [pro]

Mode:
  --mode auto            (default) auto-detect: diff if committed, new-skill if not
  --mode new             Force new-skill self-check (Phase 0 trim)            [pro]
  --mode diff            Force diff against git baseline. Fails if no baseline.

Model:
  --oracle-model <id>    (default: claude-haiku-4-5-20251001)

Other:
  --old <git-ref>        Git ref for baseline (default: HEAD)
  --adapter <name>       Selects threshold + char limit from config
  --threshold <int>      Explicit threshold override
  --out <path>           Report output path
  --quiet                Suppress terminal output
```

### Oracle models

| Model                        | Cost  | Use for                                  |
|------------------------------|-------|------------------------------------------|
| `claude-haiku-4-5-20251001`  | ~1×   | Routine CI / pre-commit (default)        |
| `claude-sonnet-4-6`          | ~6×   | Pre-merge, higher-accuracy atom extract  |
| `claude-opus-4-6`            | ~20×  | Maximum fidelity, complex skills         |

### Exit codes

| Code | Meaning                        |
|------|--------------------------------|
| `0`  | Passed threshold               |
| `1`  | Below threshold                |
| `2`  | Error (no baseline / API)      |
| `3`  | Pro plan required (upgrade at agentfactory.dev) |

---

## All Scenarios

### Scenario A — Existing global skill, diff mode (baseline behaviour, free)

```
  python3 skill-completeness-check.py --skill git-versioning --adapter claude

  is_new_skill("HEAD", ".ai/skills/git-versioning/SKILL.md")
          │
          └─ False (committed)
          │
          ▼
  git show HEAD:.ai/skills/git-versioning/SKILL.md  → original
  read .ai/skills/git-versioning/SKILL.md           → trimmed
          │
  Phase 1 — Extract atoms from original (ephemeral cache)
  Phase 2 — Verify atoms in trimmed
          │
          ▼
  report["mode"] = "diff"  |  report["old_ref"] = "HEAD"

  ════════════════════════════════════════════════════════════
    skill-completeness-check
    Skill  : git-versioning
    Old    : HEAD (v1.3.0)
    New    : .ai/skills/git-versioning/SKILL.md (v1.3.0)
    Adapter: claude   Model: claude-haiku-4-5-20251001
  ════════════════════════════════════════════════════════════

  PASSED: score 98% meets threshold 90%
```

---

### Scenario B — New global skill, auto-detected (pro gate)

```
  python3 skill-completeness-check.py --skill my-new-skill --adapter claude

  is_new_skill("HEAD", ".ai/skills/my-new-skill/SKILL.md") → True
          │
          ▼  [pro plan required]
  read .ai/skills/my-new-skill/SKILL.md  → original content
          │
  ╔═══════════════════════════════════════════════════════════╗
  ║  Phase 0 — Auto-trim              [NEW SKILL MODE]        ║
  ║  Model: claude-haiku-4-5-20251001 (default)               ║
  ║  Limit: 18,000 chars (claude adapter)                     ║
  ║  Output: trimmed_content (in-memory, never on disk)       ║
  ╚═══════════════════════════════════════════════════════════╝
          │
  Phase 1 — Extract atoms from original (ephemeral cache)
  Phase 2 — Verify atoms in trimmed_content
          │
          ▼
  report["mode"] = "new_skill"  |  report["old_ref"] = "working_tree"

  ════════════════════════════════════════════════════════════
    skill-completeness-check  [NEW SKILL SELF-CHECK]
    Skill  : my-new-skill
    Mode   : new skill — auto-trimmed to 18,000 chars
    Adapter: claude   Model: claude-haiku-4-5-20251001
  ════════════════════════════════════════════════════════════

  ● New-skill self-check complete (Phase 0 trim used tokens).
    Commit first, then re-run to compare against the baseline.
```

---

### Scenario C — Force new mode on committed skill (cross-adapter preview)

```
  python3 skill-completeness-check.py --skill git-versioning --mode new --adapter codex

  [pro plan required — --mode new always requires pro]
  --mode new → skip is_new_skill(), always run new-skill branch
  read working tree as "original"
  Phase 0 — Auto-trim to codex limit: 10,000 chars
  Phase 1+2 — atoms + verify against trimmed
          │
          ▼
  "If you trim this skill for Codex, you retain X%"
  report["mode"] = "new_skill"  |  report["adapter"] = "codex"

  Use case: preview what trimming would cost before switching adapters.
```

---

### Scenario D — Existing agent, all skills checked (pro)

```
  python3 skill-completeness-check.py --agent test-agent --adapter claude

  [pro plan required — --agent always requires pro]
  find_agent_skills("test-agent")
  → [("git-versioning", ".ai/agents/test-agent/skills/git-versioning/SKILL.md")]

  For each skill:
  ┌──────────────────────────────────────────────────────────┐
  │ is_new_skill("HEAD", skill_path)?                        │
  │   False → diff mode (git show baseline)                  │
  │   True  → new-skill mode (Phase 0 trim)                  │
  └──────────────────────────────────────────────────────────┘
  Phase 1 + Phase 2 per skill
  report → .ai/reports/agent-test-agent-git-versioning-completeness.json

  ╔══════════════════════════════════════════════════════════════╗
  ║  Agent Completeness: test-agent                              ║
  ╠══════════════════════════════════════════════════════════════╣
  ║  git-versioning        98%  ✓  diff                         ║
  ╚══════════════════════════════════════════════════════════════╝

  PASSED: 1/1 skills meet threshold (90%)
```

---

### Scenario E — New agent, all skills new (Phase 0 per skill)

```
  python3 skill-completeness-check.py --agent my-new-agent --adapter claude

  find_agent_skills("my-new-agent")
  → [("search", "..."), ("auth", "...")]

  Both → is_new_skill = True → Phase 0 auto-trim per skill

  ╔══════════════════════════════════════════════════════════════╗
  ║  Agent Completeness: my-new-agent  [NEW SKILL SELF-CHECK]   ║
  ╠══════════════════════════════════════════════════════════════╣
  ║  search                 95%  ✓  [NEW]                       ║
  ║  auth                   87%  ✗  [NEW]                       ║
  ╚══════════════════════════════════════════════════════════════╝

  FAILED: 1/2 skills below threshold (90%)
  exit 1
```

---

### Scenario F — --mode diff, no baseline → hard fail with hint

```
  python3 skill-completeness-check.py --skill my-new-skill --mode diff

  --mode diff → new_skill = False → tries git show
  → git show fails → RuntimeError
          │
          ▼
  Error: git show HEAD:.ai/skills/my-new-skill/SKILL.md failed: ...
  Hint:  Skill has no committed baseline. Use --mode new for a self-check.
  exit 2
```

---

### Scenario G — Agent with mixed skills (some committed, some new)

```
  python3 skill-completeness-check.py --agent my-agent --adapter claude

  find_agent_skills → git-versioning (committed) + new-search (not committed)

  git-versioning: is_new_skill = False → diff mode
  new-search:     is_new_skill = True  → new-skill mode (Phase 0)

  ╔══════════════════════════════════════════════════════════════╗
  ║  Agent Completeness: my-agent  [NEW SKILL SELF-CHECK]       ║
  ╠══════════════════════════════════════════════════════════════╣
  ║  git-versioning        98%  ✓  diff                         ║
  ║  new-search            92%  ✓  [NEW]                        ║
  ╚══════════════════════════════════════════════════════════════╝

  PASSED: 2/2 skills meet threshold (90%)
```

---

## Report Format

```
  --skill <name>  → .ai/reports/skill-<name>-completeness.json
  --agent <name>  → .ai/reports/agent-<agent>-<skill>-completeness.json

  New fields in v2.0.0:
    "mode":         "diff" | "new_skill"
    "oracle_model": "claude-haiku-4-5-20251001"
    "old_ref":      "HEAD" | "working_tree"
```

Example v2.0.0 report:

```json
{
  "skill":        "git-versioning",
  "mode":         "diff",
  "oracle_model": "claude-haiku-4-5-20251001",
  "old_ref":      "HEAD",
  "old_version":  "1.3.0",
  "new_version":  "1.3.0",
  "generated_at": "2026-04-20T12:00:00+00:00",
  "score":        98,
  "threshold":    90,
  "passed":       true,
  "summary":      { "preserved": 44, "degraded": 1, "missing": 0 },
  "atoms": [ ... ]
}
```

---

## Integration Points

### Pre-commit hook

```bash
# .git/hooks/pre-commit (or .ai/scripts/pre-commit-completeness.sh)
if git diff --cached --name-only | grep -q "SKILL.md"; then
  python3 .ai/scripts/skill-completeness-check.py --skill git-versioning --adapter claude
  [ $? -ne 0 ] && exit 1
fi
```

Exit code 3 (pro gate) should be treated as a warning, not a blocking failure, in free-tier environments.

### CI (GitHub Actions)

```yaml
- name: Skill completeness check
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  run: |
    python3 .ai/scripts/skill-completeness-check.py \
      --skill git-versioning --adapter claude --quiet
```

For agent-level CI with a pro token:

```yaml
- name: Agent completeness check
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    AGENTFACTORY_LICENSE_KEY: ${{ secrets.AGENTFACTORY_LICENSE_KEY }}
  run: |
    python3 .ai/scripts/skill-completeness-check.py \
      --agent test-agent --adapter claude --quiet
```

### Adapter swap preview (Scenario C)

Before switching an agent from Claude → Codex:

```bash
python3 .ai/scripts/skill-completeness-check.py \
  --skill git-versioning --mode new --adapter codex \
  --oracle-model claude-sonnet-4-6
```

Shows what percentage of atoms survive the 10,000-char Codex limit.

---

## How to add a new skill report

1. Write `.ai/skills/<name>/SKILL.md` following the YAML frontmatter convention.
2. Run the self-check (`--mode new` requires a Pro plan):
   ```bash
   python3 .ai/scripts/skill-completeness-check.py \
     --skill <name> --mode new --adapter claude
   ```
3. Review the report at `.ai/reports/skill-<name>-completeness.json`.
4. Commit the skill. On the next diff run the oracle will compare against HEAD.
