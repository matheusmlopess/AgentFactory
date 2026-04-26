# Issue Priority Report
<!-- version: 1.0.0 -->
<!-- generated: 2026-04-26 11:35 UTC -->
<!-- open-issues: 0 -->

Living priority matrix — regenerated automatically on every merge to `dev`.
Source: `.ai/scripts/generate-priority-report.py`  |  Spec: `docs/ISSUE-PRIORITY-SPEC.md`

## Track Overview

```
  ┌──────────────────┬───────────────────────────────────────────┐
  │  Track           │  Issues                                    │
  ├──────────────────┼───────────────────────────────────────────┤
  │  Harness / CLI   │                                             │
  │  Webapp / UI     │                                             │
  │  Platform Core   │                                             │
  │  Platform Upper  │                                             │
  └──────────────────┴───────────────────────────────────────────┘
```

## Dependency Matrix

```
  #       Depends on                Unblocks                  Title
  ──────  ────────────────────────  ────────────────────────  ────────────────────────────────────────
```

## Priority Waves

### Wave 1 — Start now — no blockers

```
  #       Effort    Track             Unblocks              Title
  ──────  ────────  ────────────────  ────────────────────  ────────────────────────────────────────
```

## Cross-Track Dependencies

Key dependencies that span tracks — these are the critical path risks:

```
  #96  FormatSwitch  ──────────────────────►  #102  adapter-add gate
  (harness/CLI)                               (harness/CLI)

  #83  GitHub OAuth  ─┬────────────────────►  #84  RBAC
  (platform-core)     ├────────────────────►  #85  Pro billing
                      └────────────────────►  #86  login/logout CLI

  #85  Pro billing   ─┬────────────────────►  #105 BYOK live checker
  (platform-core)     └────────────────────►  #90  marketplace

  #101 CI job        ──────────────────────►  #104 webapp report viewer
  (harness/CLI)                               (webapp/UI)
```

---

_Generated 2026-04-26 11:35 UTC by `generate-priority-report.py`._
_Run manually: `python3 .ai/scripts/generate-priority-report.py`_
