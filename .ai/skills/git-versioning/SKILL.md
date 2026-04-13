---
name: git-versioning
version: 1.3.0
description: >
  Git and versioning workflow assistant for any project using the versioning template.
  Handles commit, branch, PR, merge, tag, release, rollback, and inspection.
  Reads all project-specific values (remote URL, branch, versions) from
  skills/git-versioning/references/repo-state.md — no hardcoded project names.
  Enforces a session branch gate: no edits are allowed directly on the default branch.
  Trigger when the user wants to commit, push, open a PR, merge, tag, release,
  rollback an artifact, or asks "what should I do next" in a git context.
---

# Git Versioning Assistant — v1.3.0

---

## Step 0 — Load project context

**Before running any command**, read `skills/git-versioning/references/repo-state.md` to get:

- `REMOTE_URL` — the repo remote (e.g. `github.com/user/project`)
- `DEFAULT_BRANCH` — branch to never commit directly to (e.g. `main`)
- `LATEST_TAG` — current latest tag (e.g. `v1.0.0`)
- `ARTIFACT_VERSIONS` — current version of each tracked artifact

Use these values in every command and message. Never hardcode them.

If `repo-state.md` has unfilled placeholders, stop and tell the user:
> "Please fill in the Remote section of `skills/git-versioning/references/repo-state.md` before continuing."

Also check `.ai/memory/milestones.md` (if it exists) — the **Pending** table shows what issues are still open and which branch/PR phase they belong to. Use this to confirm the branch name and scope when the user asks "what should I do next."

---

## Step 0.5 — Session Branch Gate (run every session before any edit)

Run these two commands immediately after loading context:

```bash
git branch --show-current
git status --short
```

Then apply the gate:

| State | Action |
|-------|--------|
| On `DEFAULT_BRANCH`, working tree **clean** | **STOP.** Tell the user: "You're on `DEFAULT_BRANCH`. Create a branch before making any changes:" then output the branch creation command. Do not proceed until the user confirms they are on a non-default branch. |
| On `DEFAULT_BRANCH`, working tree **dirty** (uncommitted changes) | **EMERGENCY STOP.** Tell the user: "You have uncommitted changes directly on `DEFAULT_BRANCH` — this puts the stable release at risk. Stash your changes and move them to a feature branch:" then output the stash + branch + pop commands. Do not commit to `DEFAULT_BRANCH`. |
| On a non-default branch, working tree **clean** | Confirm: "Working on branch `<branch>` — ready to proceed." Continue to Step 1. |
| On a non-default branch, working tree **dirty** | Confirm: "Working on branch `<branch>` with uncommitted changes." Continue to Step 1. |

**Why this matters**: `DEFAULT_BRANCH` represents the last stable tagged release. Any direct commit to it makes rollback harder and risks overwriting a known-good state. All work — even a one-line fix — must be done on a branch, reviewed via PR, and merged cleanly.

**Never skip this gate.** Even if the user says "just make a quick fix" or "it's only a typo", direct commits to `DEFAULT_BRANCH` are always wrong.

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

Output the exact commands at each step. Replace `DEFAULT_BRANCH` and `REMOTE_URL`
with values from `repo-state.md`.

### Step 1 — Sync local default branch

```bash
git checkout DEFAULT_BRANCH
git pull
```

### Step 2 — Create a branch

```bash
git checkout -b <branch-name>
```

Branch name rules (from `repo-state.md`):
- `upgrade/<artifact-name>-vX.Y.Z`
- `feature/<description>`
- `docs/<topic>`
- `fix/<description>`

Ask the user what they're changing and suggest the correct branch name.

### Step 3 — Stage and commit

```bash
git add <specific-files>
git commit -m "<type>: <summary> — <impact>"
```

Types: `upgrade` | `feature` | `docs` | `fix` | `chore`

Examples:
- `upgrade: sdd-validator v2.0.0 → v2.1.0 — stricter vague term detection`
- `feature: add cost-aware-pipeline skill v1.0.0`
- `docs: add rollback guide`

Always stage specific files — never `git add .` or `git add -A`.

Note: the pre-commit hook (`.claude/hooks/pre-commit-check.sh`) will block the commit
if any staged `.md` files are missing version markers. Fix them with the version-enforcer
skill, then re-stage and retry.

### Step 4 — Push branch

```bash
git push -u origin <branch-name>
```

### Step 5 — Open a PR

If the **issue-writer** skill is installed, hand off PR body generation:
> "Use the issue-writer skill with this summary: [what changed, why, how to verify]"

Otherwise, create it directly:

```bash
gh pr create \
  --title "<type>: <summary>" \
  --body "$(cat <<'EOF'
## Summary
- <bullet: what changed>

## Test plan
- <bullet: how to verify>
EOF
)"
```

### Step 6 — Merge the PR

```bash
gh pr merge <number> --merge
```

### Step 7 — Clean up

```bash
git checkout DEFAULT_BRANCH
git pull
git branch -d <branch-name>
```

### Step 8 — Tag and release (only when DEFAULT_BRANCH is stable)

Determine repo-level bump using the SemVer rules in `repo-state.md`, then run **all three commands** — tag, push, and release are a single atomic step:

```bash
git tag -a vX.Y.Z -m "vX.Y.Z: <one-line summary>"
git push origin vX.Y.Z
gh release create vX.Y.Z \
  --title "vX.Y.Z — <short title>" \
  --notes "$(cat <<'EOF'
## What's new
- <bullet: what changed>
- <bullet: what changed>

## Breaking changes
- <bullet or "None">
EOF
)"
```

**`gh release create` is mandatory — never skip it.** A git tag alone is invisible on GitHub's Releases page. The release notes are what users and collaborators see when they check what changed. If the tag was already pushed without a release, run `gh release create` immediately to backfill it.

After tagging, update `repo-state.md` on a new branch → PR → merge:
- Add a row to "Current version tags"
- Update "Latest tag"

### Step 8.5 — Update Milestones (required after every merged PR or release)

1. Open `.ai/memory/milestones.md`
2. For each issue closed by this PR:
   - Move its row from **Pending → Completed**
   - Fill: Branch, PR#, short commit SHA, version tag (if released)
3. On version tag: stamp the Tag column for all newly completed rows
4. Bump the `<!-- version: X.Y.Z -->` marker on `milestones.md` (PATCH bump)
5. Stage and commit alongside other release docs:
   ```bash
   git add .ai/memory/milestones.md
   git commit -m "docs: update milestones for #<issue-list>"
   ```

**Never skip this step.** The milestones file is the project's audit trail — an issue with no entry in Completed is indistinguishable from one that was never worked on.

---

### Step 9 — Document the release

Invoke the `project-documenter` agent to log the release to `docs/DEVLOG.md`:

> "Document this release" or "update the devlog"

The agent reads the latest git log and tag, writes a new entry at the top of `docs/DEVLOG.md`, and exits. Do not write to DEVLOG manually — always use the agent so format stays consistent.

---

## Part 2 — Artifact Upgrade Workflow

### Pre-upgrade checklist

Before modifying any artifact file, verify:

```
[ ] Dependency check — does any other artifact import, chain from, or call this one?
    If yes: list them and confirm the new version is still compatible.
[ ] Interfaces — inputs/outputs still chain correctly with other artifacts?
[ ] References — does the new version need new files in references/?
    Add them before uploading to Claude.
[ ] Bump scope — PATCH / MINOR / MAJOR? (version-enforcer will apply it)
[ ] CLAUDE.md — Version landscape row will need updating
[ ] repo-state.md — Artifact versions row will need updating
[ ] Optional docs — if project has README.md or UPGRADE-GUIDE.md, they need a changelog entry
```

### Upgrade steps

```bash
# 1. Sync
git checkout DEFAULT_BRANCH && git pull

# 2. Branch
git checkout -b upgrade/<artifact-name>-vX.Y.Z

# 3. Edit the artifact file
# Run version-enforcer skill — it will:
#   a. Apply the version bump to the artifact file
#   b. Run scan-versions.sh to catch any other unversioned files
#   c. Update CLAUDE.md Version landscape
#   d. Update repo-state.md Artifact versions

# 4. Stage only specific files
git add skills/<artifact-name>/ CLAUDE.md skills/git-versioning/references/repo-state.md
git commit -m "upgrade: <artifact-name> vOLD → vNEW — <summary>"
# Pre-commit hook validates all staged .md files automatically

# 5. PR → merge → tag (Parts 1 Steps 4–8)

# 6. Re-install in Claude  ← DO NOT SKIP
#    Claude.ai → Project → Skills
#    → Find the skill → Remove it → Upload skills/<artifact-name>/ folder again
#    Git workflow complete does NOT mean Claude has the new version loaded.
```

---

## Part 3 — Rollback an Artifact

```bash
# Find the version to restore
git log --oneline skills/<artifact-name>/SKILL.md
git tag

# Restore the file at a specific tag
git show <tag-or-hash>:skills/<artifact-name>/SKILL.md \
  > skills/<artifact-name>/SKILL.md

# Commit forward (no new tag needed for rollback)
# Then PR → merge (Part 1 Steps 3–7)
# Re-install in Claude (Part 2 Step 6)
```

---

## Part 4 — Inspection Commands

```bash
git tag                                          # all version tags
git show vX.Y.Z                                  # tag details
git log --oneline                                # full commit history
git log --oneline skills/<name>/SKILL.md         # history for one artifact
git diff vA vB -- skills/<name>/SKILL.md         # artifact diff between tags
git diff vA vB                                   # all changes between tags
git checkout vX.Y.Z                              # inspect repo at tag (read-only)
git checkout DEFAULT_BRANCH                      # return to current
gh pr list                                       # open PRs
gh release view vX.Y.Z                           # release changelog
.claude/hooks/scan-versions.sh                   # show version status of all .md files
.claude/hooks/scan-versions.sh --staged          # show version status of staged files only
```

---

## Part 5 — State Assessment / Smoke Tests

### What should I do next?

1. Ask or infer: any uncommitted changes?
2. Ask or infer: on a feature branch or DEFAULT_BRANCH?
3. Check open PRs: `gh pr list`
4. Check tags: `git tag` — does current DEFAULT_BRANCH state have a tag?

Output the exact next command — no generic advice.

### Smoke tests after any artifact upgrade

Run these in the Claude project after re-installing the updated skill.
Adapt the prompts to match the project's domain.

**Test 1 — Standard trigger**
Send a request that should activate the upgraded artifact's primary function.
Expected: artifact triggers, produces expected output format.

**Test 2 — Edge / boundary trigger**
Send a request that is near the trigger boundary (ambiguous or partial match).
Expected: artifact handles gracefully — either triggers with a clarifying question or routes correctly.

**Test 3 — Non-trigger (negative test)**
Send a request that should NOT trigger the upgraded artifact.
Expected: artifact stays silent; another skill handles it if appropriate.

If any test fails: rollback via Part 3, open an issue with issue-writer skill, investigate before re-upgrading.
