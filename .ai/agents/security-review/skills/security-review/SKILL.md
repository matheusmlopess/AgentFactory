---
name: security-review
version: 1.0.0
description: Full security and architecture review producing a dated REVIEW-SECURITY-ARCHITECTURE-YYYY-MM-DD.md report.
triggers: security review, review design, architecture review, audit gaps, check security, run review
---

# security-review — v1.0.0 <!-- version: 1.0.0 -->

Generates or updates a structured security and architecture review document for any TypeScript, Python, or Go repository. Every invocation produces a dated `docs/REVIEW-SECURITY-ARCHITECTURE-YYYY-MM-DD.md` that can be tracked over time.

---

## Step 0 — Detect Mode

Check whether a dated review already exists on the current branch:

```bash
ls docs/REVIEW-SECURITY-ARCHITECTURE-*.md 2>/dev/null | sort | tail -1
```

| Condition | Mode | Action |
|-----------|------|--------|
| No file found | **new** | Create `docs/REVIEW-SECURITY-ARCHITECTURE-{TODAY}.md`, version `1.0.0` |
| File found on current branch | **update** | Read existing report, apply delta, bump minor version (`1.x.0 → 1.x+1.0`), add `> Updated: {TODAY}` below the original header |

---

## Step 1 — Index the Project

1. Read `project-index.yml` if present — use as authoritative component list
2. Otherwise scan `src/` for all non-test source files
3. Detect project type: check for `package.json`, `pyproject.toml`, `go.mod`
4. Build the component table (used in §1 of the report):

| Column | Description |
|--------|-------------|
| `#` | Row number |
| `File` | Relative path |
| `Wave` | Wave/sprint/layer if tracked |
| `Status` | `done`, `planned`, `stub` |
| `Working` | `✅`, `✅⚠`, `⚠️`, `❌` |
| `Notes` | One-line annotation |

---

## Step 2 — Scan Source Files for Patterns

Read every implemented source file. Grep for the following patterns and record `file:line` for each hit:

**Security patterns:**

| Pattern | SEV | Notes |
|---------|-----|-------|
| `exec(`, `execFile(`, `spawn(` | SEV-1 | No cwd/allowlist restriction |
| `readFile(` without path guard | SEV-1 | Path traversal to system files |
| `writeFile(` without path guard | SEV-1 | Arbitrary write anywhere on disk |
| `fetch(` or `axios(` without IP blocklist | SEV-1 | SSRF — localhost / cloud metadata reachable |
| `eval(` or `new Function(` | SEV-1 | Code injection |
| Plaintext secret files (`.env`, `token`) readable by tools | SEV-2 | No keychain / chmod 600 |
| `AbortSignal` absent on async loop | SEV-2 | No graceful cancel path |
| No timeout on network/shell calls | SEV-2 | DoS / hanging process |

**Design patterns:**

| Pattern | Label |
|---------|-------|
| Hardcoded version string (e.g. `'v0.2.0'` literal) | D-N |
| `Date.now()` used as unique ID | D-N |
| `void asyncFn()` with no `.catch` | D-N |
| Array/Map that grows without eviction | D-N |
| Flag/field declared but never read | D-N |
| `computeLayout()` / expensive fn in hot render path | D-N |
| Two focus models that diverge (keyboard vs mouse) | D-N |

---

## Step 3 — Build Diagrams

Produce all diagrams using GitHub-safe Mermaid syntax (see `references/mermaid-safe-patterns.md`). Adapt diagram content to the actual architecture of the target repo.

**Required diagrams:**

| # | Type | Content |
|---|------|---------|
| 1 | `graph TB` | System architecture — one subgraph per layer |
| 2 | `sequenceDiagram` | Primary business flow (agent loop, request pipeline, etc.) |
| 3 | `flowchart TD` | Data / render pipeline |
| 4 | `flowchart TD` | Input / event routing |
| 5 | `stateDiagram-v2` | Key state machine (drag, auth, job states, etc.) |
| 6 | `flowchart TD` | Dispatch / execution flow |
| 7 | `gantt` | Roadmap / wave plan |

If the repo has no stateful component, replace diagram 5 with a relevant alternative (class diagram, ER diagram).

---

## Step 4 — Classify Findings

**Security (SEV level):**
- `🔴 SEV-1` — Remote code execution, credential theft, path traversal to system files, SSRF
- `🟡 SEV-2` — Missing abort/timeout, plaintext secrets at rest, no rate limiting

Each finding must include:
- **File:** `src/path/to/file.ts`
- **Code snippet** (3–8 lines, fenced block)
- **Attack surface** — bullet list of concrete exploitation scenarios
- **Remediation** — bullet list of concrete fixes

**Design gaps (D-N):**
- Number sequentially `D-1`, `D-2`, …
- Each must include: `**File:** path:line`, code snippet, problem statement, remediation

---

## Step 5 — Recommendations Table

Classify every finding into a priority row:

```markdown
| Priority | Item | Effort | Wave/Sprint |
|----------|------|--------|-------------|
| 🔴 P0 | ... | ...h | now |
| 🟡 P1 | ... | ...h | next |
| 🟠 P2 | ... | ...h | Wave N |
| 🔵 P3 | ... | ...h | backlog |
```

Priority definitions:
- **P0** — fix before any public release
- **P1** — fix before next version tag
- **P2** — fix when working in that area
- **P3** — backlog / future wave

---

## Step 6 — Write Report

Use `references/report-template.md` as the structural skeleton. Substitute all `{{PLACEHOLDER}}` tokens with the content collected in Steps 1–5.

**New mode:**
- Create file: `docs/REVIEW-SECURITY-ARCHITECTURE-{TODAY}.md`
- First line: `<!-- version: 1.0.0 -->`
- Title: `# {PROJECT_NAME} — Security & Architecture Review — {TODAY}`

**Update mode:**
- Read existing report
- Re-run Steps 1–5
- Strike through resolved findings: `~~SEV-1 — BashTool: unrestricted shell~~ (fixed in abc1234)`
- Add any new findings discovered since the previous run
- Update Component Status Matrix rows whose status changed
- Update Recommendations Table to remove fixed items
- Bump version marker: `1.0.0 → 1.1.0`
- Add below the title: `> Updated: {TODAY}`
- Keep original creation date in the filename — it is the review cycle identifier
