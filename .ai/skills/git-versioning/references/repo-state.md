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
| v2.1.0 | da02586 | .ai/ harness consolidation + agent-gen init + complete adapter wiring |
| v2.1.1 | 91313c3 | Harness cleanup + audit gap detection (version drift, repo-state staleness) |
| v2.2.0 | c2d5dfc | git-versioning v1.2.0: session branch gate enforcement |
| v2.3.0 | 076ffcd | agent-gen import --from-git: remote repo import pipeline |

Latest tag: v2.3.0

---

## Artifact versions

| Artifact | Version | Path |
|----------|---------|------|
| agent-gen CLI | v0.2.0 | pyproject.toml |
| git-versioning | v1.2.1 | .ai/skills/git-versioning/SKILL.md |
| diff-visualizer | v1.1.0 | .ai/skills/diff-visualizer/SKILL.md |

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
