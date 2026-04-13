# Milestones Rule
<!-- version: 1.0.0 -->

- **Create at init:** Every project must have `.ai/memory/milestones.md` scaffolded by `agent-gen init`. It is the single source of truth for all issue and work-item tracking.
- **Update on PR merge:** When a PR closes an issue, move the row from **Pending → Completed** and fill Branch, PR#, short commit SHA, and Tag columns.
- **Update on release:** When a version tag is cut, stamp the Tag column for all items shipped in that release.
- **Version marker:** Bump the `<!-- version: X.Y.Z -->` marker (PATCH) on every update to milestones.md.
- **Deferred items:** Issues blocked on external clarification use status `deferred` and remain in Pending until unblocked.
- **No silent omissions:** Every GitHub issue or tracked work item must appear in milestones.md — either in Pending or Completed.
