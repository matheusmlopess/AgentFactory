# Issue Priority Report
<!-- version: 1.0.0 -->
<!-- generated: 2026-11-04 11:16 UTC -->
<!-- open-issues: 50 -->

Living priority matrix — regenerated automatically on every push to `main`.
Priority and effort come from the `p0`–`p3` and `size:S|M|L` labels.
Source: `.ai/scripts/generate-priority-report.py`  |  Spec: `docs/ISSUE-PRIORITY-SPEC.md`

## Track Overview

```
  ┌──────────────────┬───────────────────────────────────────────┐
  │  Track           │  Issues                                    │
  ├──────────────────┼───────────────────────────────────────────┤
  │  Harness / CLI   │  #137  #138  #139  #144  #145  #146  #147  #148  #149  #150  #151  #152  #153  #154  #155  #156  #157  #158  #159  #160  #161  #162  #163  #164  #165  #166  #167  #168  #169  #170  #171  #172  #173  #178  #179  #189  #190  #191  #194  #195  #196  #197  #198  #201  #202  #204│
  │  Webapp / UI     │                                             │
  │  Platform Core   │  #192  #193  #203                           │
  │  Platform Upper  │  #200                                       │
  └──────────────────┴───────────────────────────────────────────┘
```

## Dependency Matrix

```
  #       Depends on                Unblocks                  Title
  ──────  ────────────────────────  ────────────────────────  ────────────────────────────────────────
  #137    —                         —                         enhancement(cli): add agentfactory-gen status
  #138    —                         —                         enhancement(cli): add agentfactory-gen upgrad
  #139    —                         #178                      enhancement(cli): promote skill-completeness-
  #144    —                         —                         security(import): no checksum or signature ve
  #145    —                         —                         Skill creation pipeline: 10 CLI gaps discover
  #146    —                         —                         enhancement(cli): import atomicity + safety o
  #147    —                         —                         enhancement(cli): warn when skill version unc
  #148    —                         —                         enhancement(cli): add create-skill command wi
  #149    —                         —                         enhancement(cli): add test-skill smoke-test r
  #150    —                         —                         [Codex] Align Codex retrofit naming with CODE
  #151    —                         —                         [Codex] Add collision and recovery coverage f
  #152    —                         —                         [Codex] Teach harness doctor to validate code
  #153    —                         —                         [Codex] Add codex skills symlink to harness d
  #154    —                         —                         [Codex] Document AgentFactory prompt mapping 
  #155    —                         —                         [Codex] Add project-local .mcp.json awareness
  #156    —                         —                         [Codex] Document and inventory global ~/.code
  #157    —                         —                         [Codex] Expose global ~/.codex skills and rul
  #158    —                         —                         [Codex] Add plugin inventory awareness to Cod
  #159    —                         —                         [Codex] Define AgentFactory mapping model for
  #160    —                         —                         [Codex] Expand harness doctor to cover manage
  #161    —                         —                         [Codex] Broaden Codex retrofit profile to mat
  #162    —                         —                         [Codex] Reconcile historical harness-init rep
  #163    —                         —                         [Codex] Add Codex edge-case tests for MCP, .c
  #164    —                         —                         [Codex] Add live Codex environment verificati
  #165    —                         —                         [Gemini] Add canonical .gemini/skills support
  #166    —                         —                         [Gemini] Move Gemini canonical config from co
  #167    —                         —                         [Gemini] Generate Gemini-native .toml slash c
  #168    —                         —                         [Gemini] Project mcpServers from .mcp.json in
  #169    —                         —                         [Gemini] Update harness doctor to validate th
  #170    —                         —                         [Gemini] Align Gemini retrofit, generation, a
  #171    —                         —                         [Gemini] Update Gemini docs and tests to the 
  #172    —                         —                         [Codex] Tracking issue for Codex adapter alig
  #173    —                         —                         [Gemini] Tracking issue for Gemini adapter al
  #178    #139                      —                         Umbrella(cli): SKILL.md frontmatter parsing +
  #179    —                         #204                      Umbrella(cli): agent import fidelity & ergono
  #189    #191                      #190 #200                 refactor(librarian): split librarian.py and s
  #190    #189                      —                         refactor(cli): split cli.py per command group
  #191    —                         #189                      ci: type checking, formatting, dependency and
  #192    —                         —                         api: production readiness (database, containe
  #193    —                         #203                      feat(api): registry router for publish / fetc
  #194    —                         #200                      feat(orchestrate): load and write the canonic
  #195    —                         #196                      feat(orchestrate): DAG and checkpoint executi
  #196    #195                      #197                      feat(orchestrate): delegate steps and nested 
  #197    #196                      —                         feat(orchestrate): workflows in Portable Unit
  #198    —                         —                         fix(brief): agent registry links point to doc
  #200    #189 #194                 —                         spike: shared Rust contracts core (validation
  #201    —                         #203                      feat(auth): CLI device login — /auth/cli/devi
  #202    —                         —                         refactor: one API base-URL setting `AGENTFACT
  #203    #193 #201                 #204                      ops: deploy the API (api.agentfactory.dev)
  #204    #179 #203                 —                         test(e2e): MVP walkthrough — publish → webapp
```

## Priority Waves

### Wave 1 — Start now — no blockers

```
  #       Pri  Effort    Track             Unblocks              Title
  ──────  ───  ────────  ────────────────  ────────────────────  ────────────────────────────────────────
  #144    p1   medium    Harness / CLI     —                     security(import): no checksum or signature ve
  #146    p1   medium    Harness / CLI     —                     enhancement(cli): import atomicity + safety o
  #179    p1   large     Harness / CLI     #204                  Umbrella(cli): agent import fidelity & ergono
  #191    p1   medium    Harness / CLI     #189                  ci: type checking, formatting, dependency and
  #192    p1   medium    Platform Core     —                     api: production readiness (database, containe
  #193    p1   large     Platform Core     #203                  feat(api): registry router for publish / fetc
  #201    p1   large     Harness / CLI     #203                  feat(auth): CLI device login — /auth/cli/devi
  #202    p1   small     Harness / CLI     —                     refactor: one API base-URL setting `AGENTFACT
  #137    p2   medium    Harness / CLI     —                     enhancement(cli): add agentfactory-gen status
  #138    p2   large     Harness / CLI     —                     enhancement(cli): add agentfactory-gen upgrad
  #139    p2   medium    Harness / CLI     #178                  enhancement(cli): promote skill-completeness-
  #145    p2   large     Harness / CLI     —                     Skill creation pipeline: 10 CLI gaps discover
  #147    p2   small     Harness / CLI     —                     enhancement(cli): warn when skill version unc
  #148    p2   medium    Harness / CLI     —                     enhancement(cli): add create-skill command wi
  #149    p2   medium    Harness / CLI     —                     enhancement(cli): add test-skill smoke-test r
  #150    p2   small     Harness / CLI     —                     [Codex] Align Codex retrofit naming with CODE
  #151    p2   medium    Harness / CLI     —                     [Codex] Add collision and recovery coverage f
  #155    p2   medium    Harness / CLI     —                     [Codex] Add project-local .mcp.json awareness
  #160    p2   medium    Harness / CLI     —                     [Codex] Expand harness doctor to cover manage
  #161    p2   medium    Harness / CLI     —                     [Codex] Broaden Codex retrofit profile to mat
  #163    p2   medium    Harness / CLI     —                     [Codex] Add Codex edge-case tests for MCP, .c
  #194    p2   medium    Harness / CLI     #200                  feat(orchestrate): load and write the canonic
  #195    p2   large     Harness / CLI     #196                  feat(orchestrate): DAG and checkpoint executi
  #152    p3   small     Harness / CLI     —                     [Codex] Teach harness doctor to validate code
  #153    p3   small     Harness / CLI     —                     [Codex] Add codex skills symlink to harness d
  #154    p3   small     Harness / CLI     —                     [Codex] Document AgentFactory prompt mapping 
  #156    p3   small     Harness / CLI     —                     [Codex] Document and inventory global ~/.code
  #157    p3   small     Harness / CLI     —                     [Codex] Expose global ~/.codex skills and rul
  #158    p3   medium    Harness / CLI     —                     [Codex] Add plugin inventory awareness to Cod
  #159    p3   medium    Harness / CLI     —                     [Codex] Define AgentFactory mapping model for
  #162    p3   small     Harness / CLI     —                     [Codex] Reconcile historical harness-init rep
  #164    p3   medium    Harness / CLI     —                     [Codex] Add live Codex environment verificati
  #165    p3   medium    Harness / CLI     —                     [Gemini] Add canonical .gemini/skills support
  #166    p3   medium    Harness / CLI     —                     [Gemini] Move Gemini canonical config from co
  #167    p3   medium    Harness / CLI     —                     [Gemini] Generate Gemini-native .toml slash c
  #168    p3   medium    Harness / CLI     —                     [Gemini] Project mcpServers from .mcp.json in
  #169    p3   medium    Harness / CLI     —                     [Gemini] Update harness doctor to validate th
  #170    p3   medium    Harness / CLI     —                     [Gemini] Align Gemini retrofit, generation, a
  #171    p3   medium    Harness / CLI     —                     [Gemini] Update Gemini docs and tests to the 
  #172    p3   small     Harness / CLI     —                     [Codex] Tracking issue for Codex adapter alig
  #173    p3   medium    Harness / CLI     —                     [Gemini] Tracking issue for Gemini adapter al
  #198    p3   small     Harness / CLI     —                     fix(brief): agent registry links point to doc
```

### Wave 2 — After Wave 1

```
  #       Pri  Effort    Track             Unblocks              Title
  ──────  ───  ────────  ────────────────  ────────────────────  ────────────────────────────────────────
  #203    p1   medium    Platform Core     #204                  ops: deploy the API (api.agentfactory.dev)
  #178    p2   large     Harness / CLI     —                     Umbrella(cli): SKILL.md frontmatter parsing +
  #189    p2   large     Harness / CLI     #190 #200             refactor(librarian): split librarian.py and s
  #196    p2   large     Harness / CLI     #197                  feat(orchestrate): delegate steps and nested 
```

### Wave 3 — After Wave 2

```
  #       Pri  Effort    Track             Unblocks              Title
  ──────  ───  ────────  ────────────────  ────────────────────  ────────────────────────────────────────
  #204    p1   medium    Harness / CLI     —                     test(e2e): MVP walkthrough — publish → webapp
  #190    p2   large     Harness / CLI     —                     refactor(cli): split cli.py per command group
  #197    p2   medium    Harness / CLI     —                     feat(orchestrate): workflows in Portable Unit
  #200    p3   large     Platform Upper    —                     spike: shared Rust contracts core (validation
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

_Generated 2026-11-04 11:16 UTC by `generate-priority-report.py`._
_Run manually: `python3 .ai/scripts/generate-priority-report.py`_
