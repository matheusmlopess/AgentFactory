# Repo State Reference
<!-- version: 1.0.0 -->

Keep this file updated whenever skills are upgraded or tags are created.
The git-versioning skill reads this to give accurate, repo-specific commands.

---

## Remote

- URL: github.com/matheusmlopess/AgentFactory
- Default branch: dev
- Releases: github.com/matheusmlopess/AgentFactory/releases

---

## Current version tags

| Tag | Commit | What it represents |
|-----|--------|--------------------|
| v2.0.0 | b6d8f46 | Unified multi-CLI harness + Librarian intelligence layer |

Latest tag: v2.0.0

---

## Artifact versions

| Artifact | Version | Path |
|----------|---------|------|
| agent-gen CLI | v0.2.0 | pyproject.toml |
| git-versioning | v1.1.0 | .ai/skills/git-versioning/SKILL.md |
| diff-visualizer | v1.1.0 | .ai/skills/diff-visualizer/SKILL.md |
| security-review | v1.0.0 | .ai/skills/security-review/SKILL.md |

---

## SemVer bump rules for this repo

| Change | Bump |
|--------|------|
| Typo, doc fix, additive schema field | PATCH |
| Skill upgraded, new feature, new skill added, new command | MINOR |
| Breaking install convention, skill removed, CLI API change | MAJOR |

---

## Branch naming convention

  upgrade/<skill-name>-vX.Y.Z
  feature/<description>
  docs/<topic>
  fix/<description>

---

## How to update this file

After every tag + release, update:
1. "Current version tags" table — add new row, update "Latest tag"
2. "Artifact versions" table — update version for upgraded artifacts
