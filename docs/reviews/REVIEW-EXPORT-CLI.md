# Review — `agentfactory-gen export` (design, gaps, infra, doc tracking)
<!-- version: 1.0.0 -->

PR: #180 · Consolidated analysis of the `export` command and its surrounding
processes. Pairs with `docs/FEATURE-EXPORT-CLI.md` and
`docs/TESTING-EXPORT-CLI-E2E.md`.

> **Scope note (honesty first).** `export` is a **CLI command** in
> `src/agent_gen/cli.py`. It does not introduce services, routes, an operator
> console, or deployment logic. Sections on infrastructure and "operator
> console / route-separated workflow" are included as **explicit alignment
> checks** and are marked **N/A with reasoning** where they do not apply, rather
> than fabricated.

---

## 1. Design reasoning & trade-offs

```
  ┌─ decision ───────────────────┬─ alternatives ───────────────┬─ why this one ─────────────────┐
  │ branch + PR (never main)     │ direct push to main          │ exports are proposals; keeps a │
  │                              │                              │ human in the merge loop        │
  │ record source at import      │ ask for --git every time     │ round-trip by name; one source │
  │                              │                              │ of truth on disk               │
  │ copy whole TRACKED_DIRS      │ 3-way merge / per-file diff  │ simple, predictable; the local │
  │ (replace upstream agent dir) │                              │ agent IS the patch             │
  │ auto-detect agent/ subpath   │ require --subpath always     │ matches bundle layout; override│
  │                              │                              │ stays available                │
  │ accept file:// + local path  │ URL-only (like import)       │ offline + deterministic tests; │
  │                              │                              │ also nudges #179 gap 2         │
  │ reuse subprocess git         │ GitPython dependency         │ zero new deps; mirrors existing│
  │                              │                              │ _clone_and_prepare style       │
  └──────────────────────────────┴───────────────────────────────┴────────────────────────────────┘
```

Primary trade-off: **whole-directory replace** is intentionally dumb. It cannot
do a semantic merge, but it is predictable and review-gated — the PR diff shows
exactly what changes, and a maintainer resolves conflicts in the source repo.

---

## 2. Assumptions made by the implementation

```
  A1  The local agent dir is the authoritative version of the patch.
  A2  The agent lives at agent/ (or repo root) in the source — auto-detected,
      override with --subpath.
  A3  `origin` of the freshly cloned source is the correct push target
      (no fork/upstream split handled yet).
  A4  Tracked content = TRACKED_DIRS + agent-manifest.json. Files outside those
      (e.g. a source-side README) are out of scope and untouched.
  A5  The operator has push rights to the source (or will use --no-push).
  A6  `gh` is configured when --pr is used; absence is non-fatal (branch pushed).
  A7  git identity is supplied per-commit (AgentFactory) so no global config is needed.
```

---

## 3. Identified gaps & risks

```
  ┌─ id ─┬─ gap / risk ──────────────────────────────────┬─ severity ─┬─ mitigation today ───────────┐
  │ G1   │ no fork workflow (always pushes to origin)     │ medium     │ --no-push patch; or clone a  │
  │      │                                                │            │ fork and pass --git <fork>   │
  │ G2   │ whole-dir replace deletes upstream-only files  │ medium     │ documented (§6 feature doc); │
  │      │ inside a tracked dir                           │            │ PR diff makes it visible     │
  │ G3   │ branch reuse: re-export to an existing remote  │ low        │ pass a unique --branch       │
  │      │ branch may need a force/--no-ff                │            │                              │
  │ G4   │ no signature/provenance on the export commit   │ low        │ commit author is fixed+clear │
  │ G5   │ source recorded only for --from-git/-registry, │ low        │ pass --git explicitly        │
  │      │ not for ZIP/deploy imports                     │            │                              │
  │ G6   │ secrets in a tracked dir would be exported     │ medium     │ operator responsibility; see │
  │      │ verbatim                                       │            │ §8 safeguard S3             │
  └──────┴────────────────────────────────────────────────┴────────────┴──────────────────────────────┘
```

---

## 4. Missing scenarios (not yet covered)

```
  ✗ Fork-and-PR (push to a fork, PR to upstream) — only same-origin today.
  ✗ Conflict/divergence detection (source moved since import) — relies on PR review.
  ✗ Dry-run preview of the diff before cloning/pushing (`--dry-run`).
  ✗ Multi-agent export in one invocation (`export --all`).
  ✗ Selective export (only skills/, only one file).
  ✗ Provenance: stamping the export with the local git_ref it was based on.
```

---

## 5. Potential enhancements

```
  SHORT TERM
    · --dry-run  → show the would-be diff + target branch, write nothing
    · --fork     → push to a fork remote, open PR against upstream
    · stamp manifest.source.exported_from = <local git_ref> for provenance
    · --include / --exclude globs for selective export

  LONG TERM
    · 3-way merge against the source's recorded import ref (true sync, not replace)
    · round-trip status: `agentfactory-gen status` showing local-vs-source drift
    · registry-side export (publish a new version) symmetric with --from-registry
    · signed export commits / attestation
```

---

## 6. Additional checks & safeguards to add

```
  ┌─ id ─┬─ safeguard ──────────────────────────────────────────────┬─ status ──────┐
  │ S1   │ confirm-before-push prompt (or --yes) for interactive use │ proposed      │
  │ S2   │ refuse to export if the source default branch == target   │ proposed      │
  │      │ branch (avoid accidental main writes)                     │               │
  │ S3   │ secret scan of TRACKED_DIRS before commit (warn/block)    │ proposed      │
  │ S4   │ size guard — refuse absurdly large agent dirs             │ proposed      │
  │ S5   │ path-traversal guard on --subpath                         │ ✅ implemented│
  │ S6   │ temp dir always cleaned (finally)                         │ ✅ implemented│
  │ S7   │ URL scheme allow-list                                     │ ✅ implemented│
  └──────┴───────────────────────────────────────────────────────────┴───────────────┘
```

---

## 7. Documentation tracking & review process

Verification that the docs for this feature are complete and current.

```
  ┌─ artifact ───────────────────────────────────┬─ state ──────────────────────────┐
  │ Feature doc  docs/FEATURE-EXPORT-CLI.md       │ ✅ added (this PR)               │
  │ E2E test     docs/TESTING-EXPORT-CLI-E2E.md   │ ✅ added (this PR)               │
  │ Review       docs/reviews/REVIEW-EXPORT-CLI.md│ ✅ this document                 │
  │ CHANGELOG.md  [Unreleased] → Added: export     │ ✅ updated                       │
  │ CLI --help    export + options                 │ ✅ generated from Click          │
  │ Tests         src/tests/test_export.py (5)     │ ✅ added, passing                │
  │ README.md     command list                     │ ◻ optional — add export to the   │
  │                                               │   command table when merged      │
  └───────────────────────────────────────────────┴──────────────────────────────────┘
```

**Architecture / workflow diagrams:** the round-trip, execution flow, and
control-flow/ownership boundaries are diagrammed in
`docs/FEATURE-EXPORT-CLI.md` §2/§4/§9 (box-drawing, terminal-safe).

**Design & decision record:** §1 (trade-offs) + §2 (assumptions) of this doc.

**"Operator Console Route-Separated Workflow System":** **N/A.** This repo has
no operator console and no route-separated workflow surface. The CLI is invoked
directly (`agentfactory-gen export`); there is no HTTP route, dispatcher, or
console mediating it. If/when the registry API (`agent_gen.api`) grows an export
endpoint, this section should be revisited.

---

## 8. Infrastructure configuration alignment

Honest audit of the ops/infra checklist against the actual repo.

```
  WHAT EXISTS
    docker-compose.yml   services: api (uvicorn agent_gen.api.main:app) + db (postgres:16)
    Dockerfile.api       builds the registry API image
    api/openapi.json     registry API spec
    Ansible              none in this repo
    operator console     none
    routes               none (FastAPI app is the registry; no per-route workflow system)
```

```
  ┌─ checklist item ─────────────────────────┬─ verdict ───────────────────────────────────┐
  │ Docker Compose: services updated          │ NO CHANGE NEEDED — export is a CLI command;  │
  │                                           │ it adds no service, port, or dependency.     │
  │ Compose: env vars                         │ NO CHANGE — export reads no env; uses git/gh │
  │                                           │ already available to the operator.           │
  │ Compose: networks/volumes/deps            │ NO CHANGE — unaffected.                      │
  │ Ansible playbooks/roles/inventory/secrets │ N/A — repo has no Ansible.                   │
  │ Drift (code ↔ infra)                      │ NONE introduced — export does not touch the  │
  │                                           │ api service or its image.                    │
  │ Obsolete services/tasks/vars              │ NONE — nothing removed or deprecated.        │
  │ Missing infra updates for this feature    │ NONE — feature is infra-neutral by design.   │
  └───────────────────────────────────────────┴───────────────────────────────────────────────┘
```

**Validation steps used to confirm correctness**
```
  1. git diff --stat origin/main..HEAD   → only src/agent_gen/cli.py, src/tests/test_export.py,
                                            CHANGELOG.md, docs/* changed (no compose/Dockerfile/api)
  2. grep -rn "export" docker-compose.yml api/  → no coupling
  3. docker compose config (lint)        → unchanged file still valid
```

**How configuration changes are tracked & reviewed**
```
  · Infra files live beside code in the same repo → reviewed in the same PR.
  · CHANGELOG [Unreleased] records user-facing changes.
  · CI (docs/CICD-WORKFLOW.md) runs the test suite on the PR.
```

**How this is enforced in the PR process — checklist**
```
  PR CHECKLIST (export-class / infra-touching changes)
    [ ] If a service/port/env/volume changed → docker-compose.yml updated
    [ ] If the API surface changed          → api/openapi.json regenerated
    [ ] CHANGELOG [Unreleased] entry added
    [ ] Tests added/updated and green (minus known live-adapter tests)
    [ ] Docs added/updated (feature + test + review)
  FAILURE CONDITIONS (block merge)
    ✗ a new env var used in code but absent from compose / .env.example
    ✗ api route added but openapi.json stale
    ✗ test suite regressions beyond the 2 known live gemini/codex auth tests
```

**Common mismatch scenarios & required fixes** (for future infra-touching PRs)
```
  mismatch: code reads AGENTFACTORY_X, compose doesn't define it
    fix:    add it to docker-compose.yml `environment:` and .env.example
  mismatch: api endpoint added, openapi.json not regenerated
    fix:    regenerate api/openapi.json; commit alongside the route
  mismatch: db schema change, no migration
    fix:    add the migration; note in CHANGELOG
  (export PR #180 triggers NONE of these — it is CLI-only.)
```

---

## 9. Verdict

```
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ export is a focused, well-isolated, test-covered CLI addition that closes │
  │ the import round trip. It is infra-neutral (no compose/api/ansible drift).│
  │ Ship it; track the medium-severity gaps (fork workflow G1, dir-replace    │
  │ deletes G2, secret exposure G6) and the proposed safeguards (S1–S4) as    │
  │ follow-ups.                                                               │
  └──────────────────────────────────────────────────────────────────────────┘
```
