<!-- version: 1.0.0 -->
# Skill: security-review — v1.0.0 <!-- version: 1.0.0 -->

Feature documentation for the `security-review` skill packaged inside the `security-review` agent.

---

## Purpose

Produces a structured, dated security and architecture review document for any TypeScript, Python, or Go repository. Every output is reproducible — the same repo scanned twice with no changes produces structurally identical reports.

---

## Invocation

| Command | Effect |
|---------|--------|
| `/security-review` | Auto-detects mode (new or update) and runs full review |
| `/security-review new` | Forces new mode even if a report already exists |
| `/security-review update` | Forces update mode on the most recent dated report |

The skill is triggered by the following phrases:
- "security review", "review design", "architecture review"
- "audit gaps", "check security", "run review"

---

## Two Modes

### New Mode

Triggered when no `docs/REVIEW-SECURITY-ARCHITECTURE-*.md` exists on the current branch.

Output: `docs/REVIEW-SECURITY-ARCHITECTURE-{TODAY}.md`

- Version marker: `<!-- version: 1.0.0 -->`
- Title: `# {project} — Security & Architecture Review — {TODAY}`
- All 11 sections generated from scratch

### Update Mode

Triggered when a dated report already exists on the current branch (same worktree/PR cycle).

Output: same filename as existing report (date preserved — it identifies the review cycle)

- Bumps version: `1.0.x → 1.1.0`
- Adds `> Updated: {TODAY}` below original title
- Strikes through resolved findings: `~~SEV-1 — BashTool~~ (fixed in abc1234)`
- Adds new findings if discovered
- Updates Component Status Matrix rows that changed
- Trims fixed items from Recommendations Table

---

## Output Format Schema

All reports follow the exact same 11-section structure (defined in `references/report-template.md`):

| Section | Content | Mermaid type |
|---------|---------|--------------|
| 1 | Component Status Matrix | — (table) |
| 2 | System Architecture | `graph TB` |
| 3 | Primary Business Flow | `sequenceDiagram` |
| 4 | Data / Render Pipeline | `flowchart TD` |
| 5 | Input / Event Routing | `flowchart TD` |
| 6 | Key State Machine | `stateDiagram-v2` |
| 7 | Dispatch / Execution Flow | `flowchart TD` |
| 8 | Roadmap | `gantt` |
| 9 | Security Gaps | — (prose + code) |
| 10 | Design Gaps | — (prose + code) |
| 11 | Recommendations Table | — (table) |

---

## Diagram Safety

All Mermaid diagrams are produced using GitHub-safe syntax. The constraints are documented in `references/mermaid-safe-patterns.md` and enforced at generation time.

Key rules enforced:
- All node labels wrapped in `"double quotes"`
- No `()`, `/`, `<`, `{`, `}` in unquoted positions
- `sequenceDiagram` participant aliases contain no special characters
- `stateDiagram-v2` never has duplicate `note right of <state>` blocks
- `gantt` section titles use `-` not `—`

---

## Finding Classification

| Level | Emoji | Trigger |
|-------|-------|---------|
| SEV-1 | 🔴 | RCE, credential theft, path traversal, SSRF |
| SEV-2 | 🟡 | Missing abort/timeout, plaintext secrets, no rate limiting |
| D-N | — | Design gaps numbered sequentially |

Each finding includes: file path, code snippet (3–8 lines), attack surface or failure mode, and concrete remediation steps.

---

## References

| File | Purpose |
|------|---------|
| `references/report-template.md` | Full schematic skeleton with `{{PLACEHOLDER}}` tokens |
| `references/mermaid-safe-patterns.md` | GitHub Mermaid constraint reference |

---

## Historical Reports Convention

Reports accumulate in `docs/` as:
```
docs/REVIEW-SECURITY-ARCHITECTURE-2026-04-27.md   ← initial review
docs/REVIEW-SECURITY-ARCHITECTURE-2026-05-10.md   ← new review cycle
docs/REVIEW-SECURITY-ARCHITECTURE-2026-06-01.md   ← next cycle
```

The date is the review cycle identifier, not the write date of the last update. A report updated on the same branch keeps its original date.
