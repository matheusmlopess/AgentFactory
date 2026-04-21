# Issue Priority Report
<!-- version: 1.0.0 -->
<!-- generated: 2026-04-21 11:34 UTC -->
<!-- open-issues: 16 -->

Living priority matrix — regenerated automatically on every merge to `dev`.
Source: `.ai/scripts/generate-priority-report.py`  |  Spec: `docs/ISSUE-PRIORITY-SPEC.md`

## Track Overview

```
  ┌──────────────────┬───────────────────────────────────────────┐
  │  Track           │  Issues                                    │
  ├──────────────────┼───────────────────────────────────────────┤
  │  Harness / CLI   │                                             │
  │  Webapp / UI     │  #88  #105                                  │
  │  Platform Core   │  #77  #82  #84  #85  #86  #114              │
  │  Platform Upper  │  #87  #89  #90  #91  #92  #116  #117  #118  │
  └──────────────────┴───────────────────────────────────────────┘
```

## Dependency Matrix

```
  #       Depends on                Unblocks                  Title
  ──────  ────────────────────────  ────────────────────────  ────────────────────────────────────────
  #77     —                         #82 #84 #85 #86 #87 #88 #89 #90 #91 #92  epic: AgentFactory production platform — free
  #82     #77                       —                         feat[P1]: CLI extensions — agentfactory-gen p
  #84     #77                       #85 #87 #89               feat[P2]: private org workspaces + RBAC (owne
  #85     #77 #84                   #89 #90 #105              feat[P2]: Pro tier billing — Stripe seat-base
  #86     #77                       —                         feat[P2]: agentfactory-gen login / logout CLI
  #87     #77 #84                   #88 #89                   feat[P3]: per-agent audit history dashboard
  #88     #77 #87                   —                         feat[P3]: agent dependency graph visualizatio
  #89     #77 #84 #85 #87           #92                       feat[P3]: Enterprise compliance export — audi
  #90     #77 #85                   #92                       feat[P4]: marketplace — paid agent listings +
  #91     #77                       —                         feat[P4]: verified agent badge — automated Li
  #92     #77 #89 #90               —                         feat[P4]: publisher revenue share — Stripe Co
  #105    #85                       —                         feat[pro]: BYOK live completeness checker in 
  #114    —                         #117                      feat[P2]: auth backend — FastAPI OAuth server
  #116    —                         —                         feat(webapp): professional architecture upgra
  #117    #114                      —                         feat(webapp): agent converter — transform Age
  #118    —                         —                         docs(webapp): completeness system study — 3-t
```

## Priority Waves

### Wave 1 — Start now — no blockers

```
  #       Effort    Track             Unblocks              Title
  ──────  ────────  ────────────────  ────────────────────  ────────────────────────────────────────
  #77     epic      Platform Core     #82 #84 #85 #86 …     epic: AgentFactory production platform — free
  #114    ?         Platform Core     #117                  feat[P2]: auth backend — FastAPI OAuth server
  #116    ?         Platform Upper    —                     feat(webapp): professional architecture upgra
  #118    ?         Platform Upper    —                     docs(webapp): completeness system study — 3-t
```

### Wave 2 — After Wave 1

```
  #       Effort    Track             Unblocks              Title
  ──────  ────────  ────────────────  ────────────────────  ────────────────────────────────────────
  #82     medium    Platform Core     —                     feat[P1]: CLI extensions — agentfactory-gen p
  #84     large     Platform Core     #85 #87 #89           feat[P2]: private org workspaces + RBAC (owne
  #86     small     Platform Core     —                     feat[P2]: agentfactory-gen login / logout CLI
  #91     medium    Platform Upper    —                     feat[P4]: verified agent badge — automated Li
  #117    ?         Platform Upper    —                     feat(webapp): agent converter — transform Age
```

### Wave 3 — After Wave 2

```
  #       Effort    Track             Unblocks              Title
  ──────  ────────  ────────────────  ────────────────────  ────────────────────────────────────────
  #85     large     Platform Core     #89 #90 #105          feat[P2]: Pro tier billing — Stripe seat-base
  #87     medium    Platform Upper    #88 #89               feat[P3]: per-agent audit history dashboard
```

### Wave 4 — Monetisation ceiling

```
  #       Effort    Track             Unblocks              Title
  ──────  ────────  ────────────────  ────────────────────  ────────────────────────────────────────
  #88     medium    Webapp / UI       —                     feat[P3]: agent dependency graph visualizatio
  #89     medium    Platform Upper    #92                   feat[P3]: Enterprise compliance export — audi
  #90     large     Platform Upper    #92                   feat[P4]: marketplace — paid agent listings +
  #105    medium    Webapp / UI       —                     feat[pro]: BYOK live completeness checker in 
```

### Wave 5 — Wave 5

```
  #       Effort    Track             Unblocks              Title
  ──────  ────────  ────────────────  ────────────────────  ────────────────────────────────────────
  #92     large     Platform Upper    —                     feat[P4]: publisher revenue share — Stripe Co
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

_Generated 2026-04-21 11:34 UTC by `generate-priority-report.py`._
_Run manually: `python3 .ai/scripts/generate-priority-report.py`_
