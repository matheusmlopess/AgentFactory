---
name: diff-visualizer
version: 1.1.1
description: >
  Generates a self-contained HTML diff report between two repo versions using
  Mermaid diagrams. It compares the full repository, categorizes changed files,
  and writes a shareable visual changelog to `assets/`. Use it when the user
  asks to compare versions, show what changed since a release, or generate a
  visual diff between tags, commits, or `HEAD`.
---

# Diff Visualizer — v1.1.1

This skill compares two git-tagged versions of the entire specbuilder-agent repo,
identifies what changed in every folder and file, generates Mermaid flowcharts
for both states (all components color-coded by status), and writes a self-contained
HTML comparison file to `assets/diff-<OLD>-to-<NEW>.html`.

**v1.1.1 change:** frontmatter description shortened to stay compatible with Codex skill manifest limits.

---

## Step 0 — Determine versions to compare

Before running any commands, identify the comparison range:

| User says | Action |
|-----------|--------|
| "show what changed", "what changed since last release", no versions given | Auto-detect: Step 1 |
| "compare v2.0.0 to v2.2.0", "diff vA to vB" | Use the two versions the user specified; skip to Step 2 |
| "compare last two releases" | Use the two most recent tags; Step 1 |

If user specifies both versions explicitly, assign them directly:
- `$OLD` = first version (e.g. `v2.0.0`)
- `$NEW` = second version (e.g. `v2.2.0`)

Then skip Step 1 and go straight to Step 2.

---

## Step 1 — Auto-detect versions

```bash
# List all tags newest-first
git tag --sort=-version:refname | head -5
```

```bash
# Most recent tag → becomes $OLD
git describe --tags --abbrev=0
```

```bash
# Second most recent tag → becomes $NEW baseline
git tag --sort=-version:refname | sed -n '2p'
```

Default behavior:
- `$OLD` = the second most recent tag (e.g. `v2.2.0`)
- `$NEW` = the most recent tag or `HEAD` (e.g. `v2.3.0`)

If only one tag exists: `$OLD` = that tag, `$NEW` = `HEAD`.

If no tags exist at all:
> "No git tags found. Create at least one with:
> `git tag -a v1.0.0 -m 'Initial release'`
> Then re-run diff-visualizer."
Stop here.

---

## Step 2 — Build the full repo change catalog

Run these commands to get a complete picture of everything that changed:

```bash
# All changed files between the two versions, with M/A/D status
git diff $OLD $NEW --name-status
```

```bash
# Summary stats
git diff $OLD $NEW --stat
```

```bash
# Top-level directory/file listing at OLD version
git ls-tree --name-only $OLD
```

```bash
# Top-level directory/file listing at NEW version
git ls-tree --name-only $NEW
```

### Component taxonomy

Group every file path into one of these components:

| Component key | Matches |
|---------------|---------|
| `skills` | Any path starting with `skills/` |
| `docs` | Any path starting with `docs/` |
| `dashboard` | Any path starting with `dashboard/` |
| `assets` | Any path starting with `assets/` |
| `root` | Any file directly at repo root (README.md, CLAUDE.md, UPGRADE-GUIDE.md, WORKFLOW.txt, INSTALL-GUIDE.md, .gitignore, etc.) |

For each component, determine its **component-level status**:

| Status | Rule |
|--------|------|
| NEW | Component directory did not exist at `$OLD`, all its files are additions |
| REMOVED | Component directory existed at `$OLD` but is gone at `$NEW` |
| MODIFIED | Component exists in both versions AND at least one file inside changed |
| UNCHANGED | Component exists in both versions AND no files changed |

For the `root` component: MODIFIED if any root-level file appears in the diff; UNCHANGED otherwise.

### Per-file catalog

Build a flat list of every file that appears in `git diff $OLD $NEW --name-status`:

```
Component    File                                       Git Status
skills       skills/sdd-orchestrator/SKILL.md           M
skills       skills/diff-visualizer/SKILL.md            A
skills       skills/git-versioning/SKILL.md             A
docs         docs/agent-spec.md                         M
root         README.md                                  M
root         UPGRADE-GUIDE.md                           M
root         .gitignore                                 M
```

Git status codes: `A` = added (NEW), `M` = modified (MODIFIED), `D` = deleted (REMOVED), `R` = renamed.

Track global counts:
- `$CHANGED_FILES_COUNT` = total files in diff
- `$NEW_FILES_COUNT`, `$MODIFIED_FILES_COUNT`, `$REMOVED_FILES_COUNT` = counts by git status

---

## Step 3 — Extract version numbers (skills only)

For each skill folder classified as NEW, MODIFIED, or REMOVED in Step 2:

**Read OLD version** (MODIFIED and REMOVED):
```bash
git show $OLD:skills/<skill-name>/SKILL.md | head -10
```
Extract the `version:` value from YAML front matter → `$OLD_SKILL_VERSION`

**Read NEW version** (MODIFIED and NEW):
```bash
head -10 skills/<skill-name>/SKILL.md
```
Extract `version:` → `$NEW_SKILL_VERSION`

**For UNCHANGED skills**, both versions are the same — read once:
```bash
head -3 skills/<skill-name>/SKILL.md | grep version
```

If a SKILL.md has no `version:` field, use `"unknown"`.

If `git show $OLD:skills/<name>/SKILL.md` fails (file didn't exist at that tag),
treat the skill as NEW regardless of catalog classification.

For non-skill files (docs, dashboard, assets, root), no version extraction is needed —
only the git status (M/A/D) matters.

---

## Step 4 — Generate the two Mermaid diagrams

Generate plain-text Mermaid `flowchart TD` diagrams. Both diagrams show the **full repo
structure** as connected components — not just skills. Color every node by its
component-level status (or individual skill status for the skills subgraph).

### Node structure

```
repo root node
    ├── SDD Pipeline subgraph (skills)
    │     └── orchestrator → all pipeline skills → OUT
    ├── Standalone Skills subgraph (git-versioning, diff-visualizer, etc.)
    ├── docs/ node
    ├── dashboard/ node
    ├── assets/ node
    └── root files node (README, CLAUDE.md, etc.)
```

**Node ID conventions — camelCase only, no hyphens:**

```
sdd-orchestrator     → sddOrchestrator
sdd-spec-generator   → sddSpecGenerator
sdd-validator        → sddValidator
traceability-linker  → traceabilityLinker
test-case-generator  → testCaseGenerator
vague-term-rewriter  → vagueTermRewriter
git-versioning       → gitVersioning
diff-visualizer      → diffVisualizer
docs/                → docsNode
dashboard/           → dashboardNode
assets/              → assetsNode
root files           → rootNode
```

**Node label format:** `"Label\n(details)"` — double quotes, `\n` for line break.
For component nodes: `"docs/\n3 files changed"` or `"docs/\nUnchanged"`.
For skill nodes: `"sdd-orchestrator\nv2.0.0"`.

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

Include all components and skills that existed at `$OLD`. Do NOT include components/skills
that are NEW. Mark REMOVED items with REMOVED color.

```
%%{init: {'theme': 'dark'}}%%
flowchart TD
    subgraph sdd ["SDD Pipeline"]
        sddOrchestrator["sdd-orchestrator\nv2.0.0"]
        sddSpecGenerator["sdd-spec-generator\nv2.0.0"]
        sddValidator["sdd-validator\nv2.0.0"]
        traceabilityLinker["traceability-linker\nv2.0.0"]
        testCaseGenerator["test-case-generator\nv2.0.0"]
        vagueTermRewriter["vague-term-rewriter\nv2.0.0"]
        OUT(["Approved Spec"])

        sddOrchestrator --> sddSpecGenerator & sddValidator & traceabilityLinker & testCaseGenerator & vagueTermRewriter
        sddSpecGenerator & sddValidator & traceabilityLinker & testCaseGenerator & vagueTermRewriter --> OUT
    end

    docsNode["docs/\n3 files"]
    dashboardNode["dashboard/\n1 file"]
    assetsNode["assets/\n2 files"]
    rootNode["Root Files\nREADME · CLAUDE.md · etc."]

    style sddOrchestrator fill:#1e293b,stroke:#60a5fa,color:#e2e8f0
    ... (all nodes at their OLD status color)
    style docsNode fill:#1e293b,stroke:#60a5fa,color:#e2e8f0
    style rootNode fill:#1e293b,stroke:#60a5fa,color:#e2e8f0
    style OUT fill:#0f172a,stroke:#60a5fa,color:#60a5fa
```

---

### NEW diagram

Include ALL components at current state. Apply color per component/skill status.
Standalone skills go in a separate subgraph. New components appear for the first time.

```
%%{init: {'theme': 'dark'}}%%
flowchart TD
    subgraph sdd ["SDD Pipeline"]
        sddOrchestrator["sdd-orchestrator\nv2.1.0"]
        sddSpecGenerator["sdd-spec-generator\nv2.1.0"]
        sddValidator["sdd-validator\nv2.0.0"]
        traceabilityLinker["traceability-linker\nv2.0.0"]
        testCaseGenerator["test-case-generator\nv2.0.0"]
        vagueTermRewriter["vague-term-rewriter\nv2.0.0"]
        OUT(["Approved Spec"])

        sddOrchestrator --> sddSpecGenerator & sddValidator & traceabilityLinker & testCaseGenerator & vagueTermRewriter
        sddSpecGenerator & sddValidator & traceabilityLinker & testCaseGenerator & vagueTermRewriter --> OUT
    end

    subgraph standalone ["Standalone Skills"]
        gitVersioning["git-versioning\nv1.0.0"]
        diffVisualizer["diff-visualizer\nv1.1.0"]
    end

    docsNode["docs/\n1 file changed"]
    dashboardNode["dashboard/\nUnchanged"]
    assetsNode["assets/\nUnchanged"]
    rootNode["Root Files\n3 files changed"]

    style sddOrchestrator fill:#1c1507,stroke:#f59e0b,color:#fef3c7
    style sddSpecGenerator fill:#1c1507,stroke:#f59e0b,color:#fef3c7
    style sddValidator fill:#1e293b,stroke:#60a5fa,color:#e2e8f0
    style gitVersioning fill:#052e16,stroke:#22c55e,color:#dcfce7
    style diffVisualizer fill:#052e16,stroke:#22c55e,color:#dcfce7
    style docsNode fill:#1c1507,stroke:#f59e0b,color:#fef3c7
    style rootNode fill:#1c1507,stroke:#f59e0b,color:#fef3c7
    style dashboardNode fill:#1e293b,stroke:#60a5fa,color:#e2e8f0
    style assetsNode fill:#1e293b,stroke:#60a5fa,color:#e2e8f0
    style OUT fill:#0f172a,stroke:#60a5fa,color:#60a5fa
```

**Mermaid formatting rules:**
- Node IDs: camelCase only, no hyphens, no spaces
- Node labels: wrap in double quotes, use `\n` for line breaks
- `style` lines reference node ID (not label text)
- No `classDef` — use individual `style` statements
- Wrap entire diagram in `<pre class="mermaid">` when inserting into HTML
- Escape `<` and `>` as `&lt;` and `&gt;` inside node labels if needed

---

## Step 5 — Resolve HTML template placeholders

Before writing the file, build all placeholder values:

| Placeholder | Source |
|-------------|--------|
| `{{OLD_VERSION}}` | `$OLD` (e.g. `v2.2.0`) |
| `{{NEW_VERSION}}` | `$NEW` (e.g. `v2.3.0` or `HEAD`) |
| `{{GENERATED_DATE}}` | Today's date in `YYYY-MM-DD` |
| `{{OLD_DIAGRAM}}` | Full Mermaid text for OLD state (Step 4) |
| `{{NEW_DIAGRAM}}` | Full Mermaid text for NEW state (Step 4) |
| `{{OLD_SKILL_COUNT}}` | Count of skill folders at `$OLD` |
| `{{NEW_SKILL_COUNT}}` | Count of skill folders at `$NEW` |
| `{{OLD_STEP_COUNT}}` | Total `## Step` headings across all OLD SKILL.md files (or `—`) |
| `{{NEW_STEP_COUNT}}` | Same for NEW state |
| `{{CHANGED_FILES_COUNT}}` | Total files in `git diff $OLD $NEW --name-status` |
| `{{NEW_COUNT}}` | Count of files with status A (added) |
| `{{MODIFIED_COUNT}}` | Count of files with status M (modified) |
| `{{REMOVED_COUNT}}` | Count of files with status D (deleted) |
| `{{UNCHANGED_COUNT}}` | Total tracked files minus changed files |
| `{{CHANGE_TABLE}}` | Pre-built `<tr>` HTML rows — one per changed file (see below) |

**Build `{{CHANGE_TABLE}}` — one `<tr>` per changed file, grouped by component:**

Rows are sorted: `skills/` first, then `docs/`, `dashboard/`, `assets/`, root files last.
Add a `<tr class="group-header">` separator row before each component group.

```html
<tr class="group-header">
  <td colspan="5">skills/</td>
</tr>
<tr>
  <td class="table-skill">sdd-orchestrator/SKILL.md</td>
  <td><span class="badge badge-modified">MODIFIED</span></td>
  <td class="table-version">v2.0.0</td>
  <td class="table-version">v2.1.0</td>
  <td class="table-notes">Cost-Aware Decision Pipeline added</td>
</tr>
<tr class="group-header">
  <td colspan="5">root files</td>
</tr>
<tr>
  <td class="table-skill">README.md</td>
  <td><span class="badge badge-modified">MODIFIED</span></td>
  <td class="table-version">—</td>
  <td class="table-version">—</td>
  <td class="table-notes">Added diff-visualizer to skills table</td>
</tr>
```

Badge class by git status: `badge-new` (A) | `badge-modified` (M) | `badge-removed` (D)
Version columns: only populate for skill SKILL.md files (from Step 3). All other files use `<span class="na">—</span>`.
Notes: one-line description of what changed. For non-skill files, derive from the file name and component context (e.g. "Updated versions table", "Added workflow diagram"). If unsure, use `"Updated"`.

---

## Step 6 — Write the HTML file

1. Read the full template from `references/html-template.md`
2. Replace every `{{PLACEHOLDER}}` token (no spaces inside braces)
3. Verify: no remaining `{{...}}` tokens; no unescaped `<`/`>` in node labels
4. Write to: `assets/diff-{{OLD_VERSION}}-to-{{NEW_VERSION}}.html`
   - Example: `assets/diff-v2.0.0-to-v2.2.0.html`
   - If `$NEW` is HEAD: `assets/diff-v2.2.0-to-HEAD.html`

The file must be self-contained — no local file references, only CDN links.

---

## Step 7 — Report to user

```
Diff visualization written to:
  assets/diff-$OLD-to-$NEW.html

Change summary ($CHANGED_FILES_COUNT files changed across all folders):
  $NEW_FILES_COUNT   added     (green)
  $MODIFIED_FILES_COUNT   modified  (amber)
  $REMOVED_FILES_COUNT   removed   (red)

Components affected:
  skills/     — $SKILLS_STATUS
  docs/       — $DOCS_STATUS
  dashboard/  — $DASHBOARD_STATUS
  assets/     — $ASSETS_STATUS
  root files  — $ROOT_STATUS

Open in any browser — no server needed.

Optional next steps:
  git add assets/diff-$OLD-to-$NEW.html
  git commit -m "docs: add diff visualization $OLD → $NEW"
  (use git-versioning skill to open a PR)
```

---

## Error handling

| Situation | Action |
|-----------|--------|
| No tags found | Stop. Show `git tag -a vX.Y.Z -m 'description'` command. |
| Specified `$OLD` tag does not exist | Stop. Run `git tag --sort=-version:refname` and show available tags. |
| `git show $OLD:skills/<name>/SKILL.md` fails | Treat skill as NEW; note the error inline. |
| No `version:` in SKILL.md front matter | Use `"unknown"` in diagrams and table. |
| Template file missing | Stop. Report: "Template not found at skills/diff-visualizer/references/html-template.md — reinstall the skill." |
| Mermaid text exceeds ~4000 characters | Split into two sub-diagrams stacked vertically in the same panel. |
| No files changed between versions | Report: "No differences found between $OLD and $NEW." and stop. |

---

## References

- HTML template: `references/html-template.md`
- Repo state (tags, current skill versions): `skills/git-versioning/references/repo-state.md`
- Git workflow: `WORKFLOW.txt`
- Upgrade guide: `UPGRADE-GUIDE.md`
