---
name: diff-visualizer
version: 1.1.2
description: Generates a self-contained HTML diff report between two repo versions using Mermaid diagrams.
triggers: compare versions, show what changed since a release, diff tags/commits/HEAD
---

# Diff Visualizer — v1.1.2 <!-- version: 1.1.2 -->

Compares two git versions, categorizes changed files, generates Mermaid flowcharts
color-coded by status, and writes a self-contained HTML report to `assets/diff-<OLD>-to-<NEW>.html`.

---

## Step 0 — Determine versions to compare

| User says | Action |
|-----------|--------|
| no versions given / "what changed since last release" | Auto-detect: Step 1 |
| "compare vA to vB" | Use specified versions; skip to Step 2 |
| "compare last two releases" | Two most recent tags; Step 1 |

If both versions are explicit: `$OLD` = first, `$NEW` = second — skip Step 1.

---

## Step 1 — Auto-detect versions

```bash
git tag --sort=-version:refname | head -5
git describe --tags --abbrev=0          # most recent → $NEW
git tag --sort=-version:refname | sed -n '2p'  # second → $OLD
```

Default: `$OLD` = second most recent tag, `$NEW` = most recent or `HEAD`.
If one tag: `$OLD` = that tag, `$NEW` = `HEAD`.
If no tags: stop and show `git tag -a v1.0.0 -m 'Initial release'`.

---

## Step 2 — Build the full repo change catalog

```bash
git diff $OLD $NEW --name-status
git diff $OLD $NEW --stat
git ls-tree --name-only $OLD
git ls-tree --name-only $NEW
```

### Component taxonomy

| Component key | Matches |
|---------------|---------|
| `skills` | `skills/` paths |
| `docs` | `docs/` paths |
| `dashboard` | `dashboard/` paths |
| `assets` | `assets/` paths |
| `root` | files directly at repo root |

Component-level status: **NEW** (dir didn't exist at `$OLD`), **REMOVED** (gone at `$NEW`), **MODIFIED** (≥1 file changed), **UNCHANGED** (no files changed). Root: MODIFIED if any root file appears in diff.

### Per-file catalog

Build a flat list from `git diff $OLD $NEW --name-status`: Component | File | Git Status (`A`=NEW, `M`=MODIFIED, `D`=REMOVED, `R`=renamed).

Track: `$CHANGED_FILES_COUNT`, `$NEW_FILES_COUNT`, `$MODIFIED_FILES_COUNT`, `$REMOVED_FILES_COUNT`.

---

## Step 3 — Extract version numbers (skills only)

For each skill classified as NEW/MODIFIED/REMOVED:
- **OLD version**: `git show $OLD:skills/<name>/SKILL.md | head -10` → extract `version:` → `$OLD_SKILL_VERSION`
- **NEW version**: `head -10 skills/<name>/SKILL.md` → extract `version:` → `$NEW_SKILL_VERSION`
- **UNCHANGED**: read once. No `version:` → use `"unknown"`.

If `git show $OLD:...` fails, treat skill as NEW. Non-skill files need no version extraction.

---

## Step 4 — Generate the two Mermaid diagrams

Generate `%%{init: {'theme': 'dark'}}%%` + `flowchart TD` diagrams. Both show the full repo structure with all components color-coded by status.

### Node structure

```
repo root
  ├── SDD Pipeline subgraph (skills)
  │     └── orchestrator → pipeline skills → OUT
  ├── Standalone Skills subgraph
  ├── docs/ node
  ├── dashboard/ node
  ├── assets/ node
  └── root files node
```

**Node IDs:** camelCase, no hyphens (e.g. `sdd-orchestrator` → `sddOrchestrator`, `docs/` → `docsNode`).

**Node labels:** `"Label\n(details)"` — skill nodes: `"sdd-orchestrator\nv2.0.0"`, component nodes: `"docs/\n3 files changed"`.

**Style colors by status:**

| Status | fill | stroke | color |
|--------|------|--------|-------|
| UNCHANGED | `#1e293b` | `#60a5fa` | `#e2e8f0` |
| MODIFIED  | `#1c1507` | `#f59e0b` | `#fef3c7` |
| NEW       | `#052e16` | `#22c55e` | `#dcfce7` |
| REMOVED   | `#1c0707` | `#f87171` | `#fee2e2` |

Use per-node `style` statements — do NOT use `classDef`.

---

### OLD diagram

Include all components/skills that existed at `$OLD`. Exclude NEW items. Mark REMOVED items with REMOVED color. Use `%%{init: {'theme': 'dark'}}%%` and `flowchart TD`.

---

### NEW diagram

Include ALL components at current state. Apply color per status. Standalone skills go in a separate subgraph.

**Mermaid formatting rules:**
- Node IDs: camelCase, no hyphens, no spaces
- Node labels: double quotes, `\n` for line breaks
- `style` lines reference node ID (not label)
- No `classDef` — use individual `style` statements
- Wrap in `<pre class="mermaid">` when inserting into HTML
- Escape `<`/`>` as `&lt;`/`&gt;` in node labels

---

## Step 5 — Resolve HTML template placeholders

| Placeholder | Source |
|-------------|--------|
| `{{OLD_VERSION}}` | `$OLD` |
| `{{NEW_VERSION}}` | `$NEW` |
| `{{GENERATED_DATE}}` | Today `YYYY-MM-DD` |
| `{{OLD_DIAGRAM}}` / `{{NEW_DIAGRAM}}` | Mermaid text from Step 4 |
| `{{OLD_SKILL_COUNT}}` / `{{NEW_SKILL_COUNT}}` | Skill folder counts |
| `{{OLD_STEP_COUNT}}` / `{{NEW_STEP_COUNT}}` | `## Step` headings across SKILL.md files |
| `{{CHANGED_FILES_COUNT}}` | Total diff files |
| `{{NEW_COUNT}}` / `{{MODIFIED_COUNT}}` / `{{REMOVED_COUNT}}` | Counts by git status |
| `{{UNCHANGED_COUNT}}` | Total tracked − changed |
| `{{CHANGE_TABLE}}` | Pre-built `<tr>` rows (see below) |

**Build `{{CHANGE_TABLE}}`:** Sort: `skills/` → `docs/` → `dashboard/` → `assets/` → root. Add `<tr class="group-header"><td colspan="5">component/</td></tr>` before each group.

Each row: `<td class="table-skill">path</td>` | `<td><span class="badge badge-{status}">STATUS</span></td>` | `<td class="table-version">vOLD</td>` | `<td class="table-version">vNEW</td>` | `<td class="table-notes">description</td>`.

Badge class: `badge-new` (A) | `badge-modified` (M) | `badge-removed` (D). Version columns only for SKILL.md files; others use `<span class="na">—</span>`.

---

## Step 6 — Write the HTML file

1. Read template from `references/html-template.md`
2. Replace every `{{PLACEHOLDER}}` (no spaces inside braces)
3. Verify no remaining `{{...}}` tokens
4. Write to: `assets/diff-$OLD-to-$NEW.html` (HEAD variant: `assets/diff-vX.Y.Z-to-HEAD.html`)

Self-contained — CDN links only, no local file references.

---

## Step 7 — Report to user

Report output path, change summary (added/modified/removed counts per component), and that it opens in any browser without a server. Suggest committing via `git-versioning` skill.

---

## Error handling

| Situation | Action |
|-----------|--------|
| No tags found | Stop. Show `git tag -a vX.Y.Z -m 'description'`. |
| Specified `$OLD` doesn't exist | Stop. Show `git tag --sort=-version:refname`. |
| `git show $OLD:skills/<name>/SKILL.md` fails | Treat skill as NEW; note inline. |
| No `version:` in SKILL.md | Use `"unknown"`. |
| Template missing | Stop. Report path and suggest reinstalling skill. |
| Mermaid text > ~4000 chars | Split into two sub-diagrams stacked vertically. |
| No files changed | Report: "No differences found between $OLD and $NEW." |

---

## References

- HTML template: `references/html-template.md`
- Repo state: `skills/git-versioning/references/repo-state.md`
- Git workflow: `WORKFLOW.txt`
