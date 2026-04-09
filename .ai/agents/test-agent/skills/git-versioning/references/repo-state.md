# Repo State Reference
<!-- version: 2.1.0 -->

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
| v2.0.0 | 764f1df | .ai/ harness consolidation — single .CLAUDE.md source of truth |
| v2.1.0 | d94ae42 | Librarian intelligence layer enhancements + registry auto-population |
| v2.1.1 | 91313c3 | Harness cleanup + audit gap detection (version drift, repo-state staleness) |

Latest tag: v2.1.1

---

## Skill versions

| Skill | Version | Path |
|-------|---------|------|
| git-versioning | v1.2.0 | skills/git-versioning/SKILL.md |
| diff-visualizer | v1.1.0 | skills/diff-visualizer/SKILL.md |

---

## SemVer bump rules for this repo

| Change | Bump |
|--------|------|
| Typo, doc fix, additive schema field | PATCH |
| Skill upgraded, new behavior, new skill added | MINOR |
| Breaking install convention, skill removed, API change | MAJOR |

---

## Branch naming convention

  upgrade/<skill-name>-vX.Y.Z
  docs/<topic>
  fix/<description>
  feature/<description>

---

## How to update this file

After every tag + release, update:
1. "Current version tags" table — add new row, update "Latest tag"
2. "Skill versions" table — update version for upgraded skills
