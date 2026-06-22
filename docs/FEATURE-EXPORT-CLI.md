# Export — patch a local agent back to its source repo
<!-- version: 1.0.0 -->

PR: #180 · Command: `agentfactory-gen export`

The inverse of `import`: take an agent you edited locally under
`.ai/agents/<name>/` and flow those changes **back upstream** to the agent's
source-of-truth git repo as a reviewable branch + PR.

---

## 1. Overview

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  PROBLEM                                                              │
  │    `import` is one-way. You import an agent, improve its SKILL.md /   │
  │    scripts in your project, and the upstream repo never sees it.      │
  │                                                                       │
  │  SOLUTION                                                             │
  │    `export <name>` clones the source, applies your local agent over  │
  │    it, commits on a branch, pushes, and opens a PR — a round trip.    │
  └──────────────────────────────────────────────────────────────────────┘
```

`import` records where an agent came from; `export` reads that and patches the
changes back. The source is never force-pushed — every export is an isolated
branch (`agentfactory/export-<name>`) and a PR, so a human reviews the merge.

---

## 2. The round trip

```
        agentfactory-gen import                 agentfactory-gen export
   ┌────────────────────────────┐          ┌────────────────────────────┐
   │  source repo (git)         │          │  .ai/agents/<name>/        │
   │    agent/ …                │          │    (your local edits)      │
   └─────────────┬──────────────┘          └─────────────┬──────────────┘
                 │  clone + register                     │  clone source
                 ▼                                        ▼
   ┌────────────────────────────┐          ┌────────────────────────────┐
   │  .ai/agents/<name>/        │          │  apply over agent/ subpath │
   │  + manifest.source = {git} │ ───────► │  branch agentfactory/      │
   │                            │  edit    │     export-<name>          │
   │                            │          │  commit · push · PR        │
   └────────────────────────────┘          └─────────────┬──────────────┘
                                                          ▼
                                              ┌────────────────────────────┐
                                              │  source repo: new PR       │
                                              │  (human reviews + merges)  │
                                              └────────────────────────────┘
```

---

## 3. Synopsis

```
  agentfactory-gen export <NAME> [options]

  ┌─ option ─────────────┬─ default ──────────────────┬─ purpose ───────────────────────┐
  │ --git URL            │ manifest.source.git        │ source repo to patch back to     │
  │ --subpath PATH       │ auto-detect (agent/ | root)│ where the agent lives upstream   │
  │ --branch NAME        │ agentfactory/export-<name> │ branch to create + push          │
  │ -m, --message TEXT   │ "agent(<name>): sync …"     │ commit message                   │
  │ --project-root PATH  │ .                          │ project holding the agent        │
  │ --push / --no-push   │ --push                     │ push branch (else write a .patch)│
  │ --pr / --no-pr       │ --pr                       │ open a PR via `gh` after push    │
  └──────────────────────┴────────────────────────────┴──────────────────────────────────┘
```

---

## 4. Execution flow (happy path)

```
  export <name>
     │
     ├─ 1. locate agent .......... .ai/agents/<name>/        (error if missing)
     ├─ 2. resolve source ........ --git ▸ manifest.source.git (error if neither)
     ├─ 3. normalize URL ......... https/git@/ssh/git:///file:// or local path
     ├─ 4. git clone source ...... temp dir                  (error on clone fail)
     ├─ 5. detect subpath ........ agent/manifest? → "agent" ; root manifest? → "" ; else "agent"
     ├─ 6. apply local agent ..... copy manifest + skills/commands/docs/scripts/orchestration
     ├─ 7. branch + add .......... git checkout -b <branch> ; git add -A
     ├─ 8. changed? ─ no ───────── "No changes to export ✓"  (exit 0, nothing pushed)
     │              └ yes
     ├─ 9. commit ................ as AgentFactory <agentfactory@local>
     ├─ 10. push ................. git push -u origin <branch>   (skipped with --no-push)
     └─ 11. PR ................... gh pr create                 (skipped with --no-pr)
```

---

## 5. Concrete examples

### 5.1 Happy path — recorded source, push + PR
```
  $ agentfactory-gen export docs-system
  [librarian] Cloning https://github.com/me/docs-system ...
  [librarian] Applying 'docs-system' → agent ...
  [librarian] Committed: 9f2c1ab agent(docs-system): sync from AgentFactory export
  [librarian] Pushing 'agentfactory/export-docs-system' to origin ...
  [librarian] PR opened: https://github.com/me/docs-system/pull/42
```

### 5.2 No recorded source — pass it explicitly
```
  $ agentfactory-gen export demo --git git@github.com:me/demo.git
```

### 5.3 Offline / no push — produce a patch you apply by hand
```
  $ agentfactory-gen export demo --no-push
  [librarian] Committed: 1a2b3c4 agent(demo): sync from AgentFactory export
  [librarian] --no-push: patch written to demo-export.patch
    apply upstream with:  git checkout -b agentfactory/export-demo && git am demo-export.patch
```

### 5.4 Push a branch but open the PR yourself
```
  $ agentfactory-gen export demo --no-pr
  [librarian] Pushed 'agentfactory/export-demo'. Open a PR from it when ready.
```

### 5.5 Nothing changed since last sync
```
  $ agentfactory-gen export demo
  [librarian] No changes to export — the source already matches. ✓
```

---

## 6. What gets applied (and what does not)

```
  COPIED over the source's agent location:
    ✔ agent-manifest.json
    ✔ skills/        ✔ commands/     ✔ docs/
    ✔ scripts/       ✔ orchestration/        (the TRACKED_DIRS)

  NOT touched:
    ✗ files in the source outside the agent location (READMEs, CI, etc.)
    ✗ the source's default branch (export only writes a feature branch)
    ✗ git history of the source (no force-push, no rewrite)
```

> A tracked directory present locally **replaces** its upstream counterpart
> (`rmtree` + `copytree`) so deletions propagate. Files the local agent does not
> have in a tracked dir are removed on the branch — intended, since the local
> agent is the source of the patch.

---

## 7. Behaviour & decisions

```
  ┌─ DECISION ───────────────────┬─ WHY ───────────────────────────────────────┐
  │ Branch + PR, never main      │ exports are proposals; a human merges        │
  │ Source recorded at import    │ no need to retype the URL; round-trip by name│
  │ Auto-detect agent/ subpath   │ matches how bundles are laid out (agent/…)   │
  │ --git accepts file:// + path │ offline use + deterministic tests            │
  │ No-op is success (exit 0)    │ safe to run in scripts / pre-commit          │
  │ Commit identity = AgentFactory│ traceable, never impersonates the operator  │
  └──────────────────────────────┴──────────────────────────────────────────────┘
```

---

## 8. Validation, errors & recovery

```
  ┌─ situation ───────────────────┬─ message ─────────────────────────┬─ recovery ─────────────────┐
  │ agent dir missing             │ "Agent '<n>' not found at …"       │ check --project-root / name │
  │ no source + no --git          │ "No source repo recorded for …"    │ pass --git URL              │
  │ bad URL / unreachable         │ "git clone failed: …"              │ fix URL / auth / network    │
  │ --subpath contains '..'       │ "must not contain '..'"            │ use a path inside the repo  │
  │ subpath escapes repo          │ "resolves outside … traversal"     │ correct --subpath           │
  │ push rejected (no write/auth) │ "git push failed: …"               │ get write access; or --no-push│
  │ gh missing / PR fails         │ "Pushed …; open a PR manually"     │ branch IS pushed; open PR by hand│
  └───────────────────────────────┴────────────────────────────────────┴─────────────────────────────┘
```

Recovery principles:
- **Idempotent & isolated** — re-running re-clones a fresh temp dir; nothing is
  left dirty in your project (temp dir is always removed in a `finally`).
- **Push failure ≠ data loss** — fall back to `--no-push` to get a `.patch`.
- **PR failure ≠ work lost** — the branch is already on the remote; open the PR
  in the GitHub UI from the printed branch name.

---

## 9. What changed in this implementation

### 9.1 File layout — before vs after
```
  BEFORE                                  AFTER
  src/agent_gen/                          src/agent_gen/
  └── cli.py                              └── cli.py
       ├── import  (one-way in)                ├── import  (now records source)
       ├── wrap                                ├── wrap
       └── publish                             ├── publish
                                               └── export  ← NEW (one-way out)
  src/tests/                              src/tests/
  └── test_cli.py …                       ├── test_cli.py …
                                          └── test_export.py  ← NEW (5 tests)
```

### 9.2 Manifest — before vs after import
```
  BEFORE (imported agent)                 AFTER (imported agent)
  {                                       {
    "name": "demo",                         "name": "demo",
    "version": "1.0.0",                      "version": "1.0.0",
    "resources": { … }                       "resources": { … },
  }                                          "source": { "git": "https://…/demo" }  ← NEW
                                          }
```

### 9.3 Behaviour — before vs after
```
  ACTION: "I improved an imported agent's SKILL.md"

  BEFORE                                   AFTER
  ──────                                   ─────
  edit .ai/agents/demo/…                   edit .ai/agents/demo/…
  ▸ no path back upstream                  ▸ agentfactory-gen export demo
  ▸ copy/paste into the source repo        ▸ → branch + PR on the source repo
    by hand, hope nothing drifts             → reviewed + merged upstream
```

Ownership boundary: the **operator** owns local edits; **export** owns the
mechanical clone→apply→branch→push; the **upstream maintainer** owns the merge.
Export never crosses that last boundary (no direct push to the default branch).

---

## 10. See also

- E2E test guide: `docs/TESTING-EXPORT-CLI-E2E.md`
- Design analysis, gaps, infra alignment: `docs/reviews/REVIEW-EXPORT-CLI.md`
- Related upstream gaps: AgentFactory#179 (import fidelity)
