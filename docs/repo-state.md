# Repo State Reference
<!-- version: 2.0.0 -->

Keep this file updated whenever artifacts/agents are upgraded or tags are created.
This file serves as the source of truth for the project's Git and versioning workflows.

---

## Remote

- URL: https://github.com/matheusmlopess/AgentFactory.git
- Default branch: dev

---

## Current version tags

| Tag | What it represents |
|-----|--------------------|
| v2.0.0 | Unified AI Harness, Standalone Skill Import, E2E Integration Tests |

Latest tag: v2.0.0

---

## Artifact versions

| Artifact | Version | Path |
|-------|---------|------|
| Unified AI Harness | v2.0.0 | core/, adapters/ |
| test-agent | v1.0.0 | agents/test-agent/ |
| test-claude-agent | v1.0.0 | agents/test-claude-agent/ |
| test-intel-agent | v1.0.0 | agents/test-intel-agent/ |

---

## SemVer bump rules for this repo

| Change | Bump |
|--------|------|
| Typo, doc fix, minor script optimization | PATCH |
| Agent upgraded, new Librarian feature, new agent added | MINOR |
| Breaking AgentFactory convention, breaking schema change | MAJOR |

---

## Branch naming convention

- `upgrade/<artifact-name>-vX.Y.Z`
- `docs/<topic>`
- `fix/<description>`
- `feature/<description>`
- `chore/<description>`

---

## How to update this file

After every tag + release, update:
1. "Current version tags" table — add new row, update "Latest tag"
2. "Artifact versions" table — update version for upgraded artifacts