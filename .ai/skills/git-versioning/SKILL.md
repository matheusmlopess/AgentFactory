---
name: git-versioning
version: 1.3.1
description: Git workflow assistant — commit, branch, PR, tag, release, rollback, and inspection.
triggers: commit, push, open a PR, merge, tag, release, rollback, "what should I do next"
---

# Git Versioning Assistant — v1.3.1

---

## Step 0 — Load project context

**Before running any command**, read `skills/git-versioning/references/repo-state.md` to get:

- `REMOTE_URL` — repo remote
- `DEFAULT_BRANCH` — branch to never commit directly to
- `LATEST_TAG` — current latest tag
- `ARTIFACT_VERSIONS` — current version of each tracked artifact

Use these values in every command. Never hardcode them.

If `repo-state.md` has unfilled placeholders, stop:
> "Please fill in the Remote section of `skills/git-versioning/references/repo-state.md` before continuing."

Also check `.ai/memory/milestones.md` (if it exists) — the **Pending** table shows open issues and branch/PR scope.

---

## Step 0.5 — Session Branch Gate (run every session before any edit)

```bash
git branch --show-current
git status --short
```

| State | Action |
|-------|--------|
| On `DEFAULT_BRANCH`, clean | **STOP.** Output branch creation command. Do not proceed. |
| On `DEFAULT_BRANCH`, dirty | **EMERGENCY STOP.** Output stash + branch + pop commands. Do not commit. |
| On non-default branch, clean | Confirm ready. Continue to Step 1. |
| On non-default branch, dirty | Confirm branch + uncommitted changes. Continue to Step 1. |

**Never skip this gate.** Direct commits to `DEFAULT_BRANCH` are always wrong.

---

## Step 1 — Identify the workflow

| User says / wants | Workflow |
|-------------------|----------|
| "commit", "save", "push" | Full git workflow (Part 1) |
| "upgrade", "update a skill/artifact" | Artifact upgrade workflow (Part 2) |
| "rollback", "restore old version" | Rollback workflow (Part 3) |
| "tag", "release", "what version" | Tag + release step only |
| "merge to DEFAULT_BRANCH", "merge the PR" | Merge step only |
| "open a PR" | PR step only |
| "what changed", "show history" | Inspection commands (Part 4) |
| "what should I do next" | State assessment → recommend next step (Part 5) |

If unclear, ask: "What are you trying to do — commit changes, upgrade an artifact, or something else?"

---

## Part 1 — Full Git Workflow

Output the exact commands at each step. Replace `DEFAULT_BRANCH` and `REMOTE_URL` with values from `repo-state.md`.

### Step 1 — Sync local default branch

```bash
git checkout DEFAULT_BRANCH
git pull
```

### Step 2 — Create a branch

```bash
git checkout -b <branch-name>
```

Branch name rules: `upgrade/<artifact>-vX.Y.Z` | `feature/<desc>` | `docs/<topic>` | `fix/<desc>`

### Step 3 — Stage and commit

```bash
git add <specific-files>
git commit -m "<type>: <summary> — <impact>"
```

Types: `upgrade` | `feature` | `docs` | `fix` | `chore`. Always stage specific files — never `git add .` or `git add -A`.

Pre-commit hook (`.claude/hooks/pre-commit-check.sh`) blocks commits if staged `.md` files lack version markers. Fix with version-enforcer skill, then re-stage and retry.

### Step 4 — Push branch

```bash
git push -u origin <branch-name>
```

### Step 5 — Open a PR

If **issue-writer** skill is installed, delegate PR body generation. Otherwise:

```bash
gh pr create --title "<type>: <summary>" --body "$(cat <<'EOF'
## Summary
- <what changed>

## Test plan
- <how to verify>
EOF
)"
```

### Step 6 — Merge the PR

```bash
gh pr merge <number> --merge
```

### Step 7 — Clean up

```bash
git checkout DEFAULT_BRANCH && git pull && git branch -d <branch-name>
```

### Step 8 — Tag and release (only when DEFAULT_BRANCH is stable)

Run integration tests first: `pytest -m integration -v --no-cov`. If any fail, do not tag.

Determine SemVer bump from `repo-state.md`, then run all three atomically:

```bash
git tag -a vX.Y.Z -m "vX.Y.Z: <one-line summary>"
git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z — <short title>" --notes "$(cat <<'EOF'
## What's new
- <bullet>

## Breaking changes
- <bullet or "None">
EOF
)"
```

**`gh release create` is mandatory — never skip it.** After tagging, update `repo-state.md` (new branch → PR → merge): add tag row, update "Latest tag".

### Step 8.5 — Update Milestones (required after every merged PR or release)

1. Open `.ai/memory/milestones.md`
2. Move closed issues from **Pending → Completed**; fill Branch, PR#, commit SHA, tag
3. On version tag: stamp Tag column for newly completed rows
4. Bump `<!-- version: X.Y.Z -->` on `milestones.md` (PATCH bump)
5. `git add .ai/memory/milestones.md && git commit -m "docs: update milestones for #<issues>"`

**Never skip this step.** The milestones file is the project's audit trail.

### Step 8.6 — Regenerate Issue Priority Report (required after every merge)

```bash
python3 .ai/scripts/generate-priority-report.py
git add docs/ISSUE-PRIORITY.md
git commit -m "docs: regenerate issue priority report"
```

This recomputes the dependency wave graph from live GitHub data. Closing the merged
issue may promote other issues to earlier waves — the report answers "what next?"
automatically. CI also runs this on push to dev/main via `issue-tracker.yml`.

---

## Part 2 — Artifact Upgrade Workflow

### Pre-upgrade checklist

```
[ ] Dependency check — other artifacts that import/call this one still compatible?
[ ] Interfaces — inputs/outputs still chain correctly?
[ ] References — new files needed in references/? Add before uploading to Claude.
[ ] Bump scope — PATCH / MINOR / MAJOR?
[ ] CLAUDE.md + repo-state.md rows need updating
```

### Upgrade steps

```bash
git checkout DEFAULT_BRANCH && git pull
git checkout -b upgrade/<artifact-name>-vX.Y.Z
# Edit artifact, run version-enforcer skill
git add skills/<artifact-name>/ CLAUDE.md skills/git-versioning/references/repo-state.md
git commit -m "upgrade: <artifact-name> vOLD → vNEW — <summary>"
# PR → merge → tag (Part 1 Steps 4–8)
# Re-install in Claude.ai → Project → Skills ← DO NOT SKIP
```

---

## Part 3 — Rollback an Artifact

```bash
git log --oneline skills/<artifact-name>/SKILL.md
git show <tag-or-hash>:skills/<artifact-name>/SKILL.md > skills/<artifact-name>/SKILL.md
# Commit forward → PR → merge (Part 1 Steps 3–7)
# Re-install in Claude (Part 2)
```

---

## Part 4 — Inspection Commands

```bash
git tag                                        # all version tags
git log --oneline                              # full history
git log --oneline skills/<name>/SKILL.md       # artifact history
git diff vA vB -- skills/<name>/SKILL.md       # artifact diff between tags
gh pr list                                     # open PRs
gh release view vX.Y.Z                         # release changelog
.claude/hooks/scan-versions.sh                 # version status of all .md files
.claude/hooks/scan-versions.sh --staged        # staged files only
```

---

## Part 5 — State Assessment / Smoke Tests

### What should I do next?

Check: uncommitted changes? feature branch or DEFAULT_BRANCH? open PRs (`gh pr list`)? current DEFAULT_BRANCH tagged (`git tag`)?

Output the exact next command — no generic advice.

### Smoke tests after any artifact upgrade

After re-installing the updated skill in Claude, send three prompts: a standard trigger, an edge/boundary case, and a non-trigger. If any fails: rollback via Part 3, open an issue, investigate before re-upgrading.
