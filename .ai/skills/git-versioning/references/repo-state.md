# Repo State Reference
<!-- version: 1.1.0 -->

Keep this file updated whenever skills are upgraded or tags are created.
The git-versioning skill reads this to give accurate, repo-specific commands.

---

## Remote

- URL: github.com/matheusmlopess/AgentFactory
- Default branch: main (there is no `dev` branch; CI runs on PRs to `main`)
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
| v2.3.1 | b6e58aa | git-versioning v1.2.1: mandatory gh release create enforcement |
| v2.3.2 | 73be793 | Rename context file from .CLAUDE.md to AgentFactory.md |
| v2.4.0 | 34eb58c | Repo cleanup: src layout, remove stale dirs, rewrite README |
| v2.4.1 | 99c09ed | Move tests/ → src/tests/, add pytest testpaths config |
| v2.4.2 | c8d45e2 | Fix test-agent description, drop stale egg-info, CHANGELOG updates |
| v2.5.0 | f5ab939 | CI/CD pipeline, traceability matrix, security fixes, 14 new tests, harness-doctor |
| v2.5.1 | f5b50b4 | Rename PyPI package to agentfactory-gen |
| v0.3.1 | cbe7036 | PyPI release 0.3.1 (agentfactory-gen) |
| v2.8.0 | c7483ec | Milestone tag (AgentFactory.md master brief, #125); no GitHub release, not on PyPI |

Latest tag: v2.8.0 (milestone). Latest PyPI release: v0.3.1.

### Version scheme (from 0.4.0)

- Tags are **package versions** only: `v` + `[project].version` in `pyproject.toml`
  (`release.yml` refuses any other tag). Next: `v0.4.0`.
- The `v2.x` tags above were milestone tags from April 2026 and are kept for history.
- `<!-- version: -->` markers in Markdown files are document versions, not package versions.

---

## Artifact versions

| Artifact | Version | Path |
|----------|---------|------|
| agentfactory-gen CLI | v0.4.0 | pyproject.toml |
| git-versioning | v1.3.1 | .ai/skills/git-versioning/SKILL.md |
| diff-visualizer | v1.1.2 | .ai/skills/diff-visualizer/SKILL.md |
| issue-tracker | v1.0.0 | .ai/skills/issue-tracker/SKILL.md |

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
