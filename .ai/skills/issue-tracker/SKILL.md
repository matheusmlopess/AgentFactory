---
name: issue-tracker
version: 1.0.0
description: Regenerates the issue priority report and dependency matrix from live GitHub data.
triggers: regenerate priority report, update issue tracker, show dependency matrix, what should I work on next
---

# Issue Tracker — v1.0.0 <!-- version: 1.0.0 -->

Regenerates `docs/ISSUE-PRIORITY.md` from live GitHub issue data. Run after every
feature merge or whenever priority guidance is needed.

---

## Step 1 — Run the generator

```bash
python3 .ai/scripts/generate-priority-report.py
```

This fetches all open issues via `gh`, computes the dependency graph, assigns waves,
and writes `docs/ISSUE-PRIORITY.md`.

**Flags:**
- `--dry-run` — print to terminal only, no file write
- `--repo owner/repo` — override the repo (default: current gh context)

---

## Step 2 — Review the output

Check the report for:

1. **"Ready to Close" section** — issues flagged as implemented. Close them:
   ```bash
   gh issue close <number> --comment "Implemented — closing per priority report."
   ```

2. **Wave 1 items** — these have no blockers and should be the active focus.

3. **Cross-track dependencies** — any wave that has large cross-track deps is a
   coordination risk. Flag it if the dep is owned by a different contributor.

---

## Step 3 — Commit the updated report

```bash
git add docs/ISSUE-PRIORITY.md
git commit -m "docs: regenerate issue priority report"
```

---

## Step 4 — Update milestones if a feature was just merged

If this run was triggered by a merge, also update `.ai/memory/milestones.md`:
- Move the merged issue from **Pending → Completed**
- Fill Branch, PR#, commit SHA, tag (if released)
- Bump `<!-- version: X.Y.Z -->` on milestones.md (PATCH bump)

---

## Error handling

| Situation | Action |
|-----------|--------|
| `gh: command not found` | Install GitHub CLI: `brew install gh` or `apt install gh` |
| `gh auth status` fails | Run `gh auth login` first |
| `docs/` directory missing | Script creates it automatically |
| Script exits non-zero | Check stderr — usually a `gh` API rate limit or auth issue |
