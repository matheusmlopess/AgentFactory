# Repo State Reference
<!-- version: 2.5.0 -->

Keep this file updated whenever skills are upgraded or tags are created.
The git-versioning skill reads this to give accurate, repo-specific commands.

---

## Remote

- URL: github.com/matheusmlopess/specbuilder-agent
- Default branch: main
- Releases: github.com/matheusmlopess/specbuilder-agent/releases

---

## Current version tags

| Tag | Commit | What it represents |
|-----|--------|--------------------|
| v2.0.0 | a45f537 | Initial commit — pre-restructure layout |
| v2.1.0 | d42674a | Clean layout (docs/, dashboard/, assets/, skills/) + sdd-orchestrator & sdd-spec-generator upgraded to v2.1.0 |
| v2.1.1 | 2674147 | Workflow docs: WORKFLOW.txt, workflow.svg, versioning section in UPGRADE-GUIDE |
| v2.2.0 | dd2eb2c | New skill: git-versioning v1.0.0 |
| v2.3.0 | 2d3455e | New skill: diff-visualizer v1.0.0 |
| v2.4.0 | ade13a7 | diff-visualizer v1.0.0 → v1.1.0 (full-repo scope) |
| v2.5.0 | 767a010 | Versioning template + hooks — version-enforcer v1.1.0, git-versioning v1.1.0, dynamic MD enforcement |

Latest tag: v2.5.0

---

## Skill versions

| Skill | Version | Path |
|-------|---------|------|
| sdd-orchestrator | v2.1.0 | skills/sdd-orchestrator/SKILL.md |
| sdd-spec-generator | v2.1.0 | skills/sdd-spec-generator/SKILL.md |
| sdd-validator | v2.0.0 | skills/sdd-validator/SKILL.md |
| traceability-linker | v2.0.0 | skills/traceability-linker/SKILL.md |
| test-case-generator | v2.0.0 | skills/test-case-generator/SKILL.md |
| vague-term-rewriter | v2.0.0 | skills/vague-term-rewriter/SKILL.md |
| git-versioning | v1.0.0 | skills/git-versioning/SKILL.md |
| diff-visualizer | v1.1.0 | skills/diff-visualizer/SKILL.md |
| issue-writer | v1.2.0 | skills/issue-writer/SKILL.md |

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
