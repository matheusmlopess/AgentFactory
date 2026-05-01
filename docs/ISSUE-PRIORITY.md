# Issue Priority Report
<!-- version: 1.0.0 -->
<!-- generated: 2026-05-01 15:24 UTC -->
<!-- open-issues: 40 -->

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
  │  Platform Upper  │  #132  #133  #134  #135  #136  #137  #138  #139  #142  #143  #144  #145  #146  #147  #148  #149  #150  #151  #152  #153  #154  #155  #156  #157  #158  #159  #160  #161  #162  #163  #164  #165  #166  #167  #168  #169  #170  #171  #172  #173│
  └──────────────────┴───────────────────────────────────────────┘
```

## Dependency Matrix

```
  #       Depends on                Unblocks                  Title
  ──────  ────────────────────────  ────────────────────────  ────────────────────────────────────────
  #132    —                         —                         bug(cli): audit exits 1 on untracked files wi
  #133    —                         —                         bug(cli): --version flag not defined on root 
  #134    —                         —                         bug+enhancement(cli): SKILL.md frontmatter no
  #135    —                         —                         bug(cli): import --project-root resolves conf
  #136    —                         —                         enhancement(cli): wrap --out flag undiscovera
  #137    —                         —                         enhancement(cli): add agentfactory-gen status
  #138    —                         —                         enhancement(cli): add agentfactory-gen upgrad
  #139    —                         —                         enhancement(cli): promote skill-completeness-
  #142    —                         —                         security(import): scripts/ in imported agents
  #143    —                         —                         security(cli): --project-root accepts path tr
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
```

## Priority Waves

### Wave 1 — Start now — no blockers

```
  #       Effort    Track             Unblocks              Title
  ──────  ────────  ────────────────  ────────────────────  ────────────────────────────────────────
  #132    ?         Platform Upper    —                     bug(cli): audit exits 1 on untracked files wi
  #133    ?         Platform Upper    —                     bug(cli): --version flag not defined on root 
  #134    ?         Platform Upper    —                     bug+enhancement(cli): SKILL.md frontmatter no
  #135    ?         Platform Upper    —                     bug(cli): import --project-root resolves conf
  #136    ?         Platform Upper    —                     enhancement(cli): wrap --out flag undiscovera
  #137    ?         Platform Upper    —                     enhancement(cli): add agentfactory-gen status
  #138    ?         Platform Upper    —                     enhancement(cli): add agentfactory-gen upgrad
  #139    ?         Platform Upper    —                     enhancement(cli): promote skill-completeness-
  #142    ?         Platform Upper    —                     security(import): scripts/ in imported agents
  #143    ?         Platform Upper    —                     security(cli): --project-root accepts path tr
  #144    ?         Platform Upper    —                     security(import): no checksum or signature ve
  #145    ?         Platform Upper    —                     Skill creation pipeline: 10 CLI gaps discover
  #146    ?         Platform Upper    —                     enhancement(cli): import atomicity + safety o
  #147    ?         Platform Upper    —                     enhancement(cli): warn when skill version unc
  #148    ?         Platform Upper    —                     enhancement(cli): add create-skill command wi
  #149    ?         Platform Upper    —                     enhancement(cli): add test-skill smoke-test r
  #150    ?         Platform Upper    —                     [Codex] Align Codex retrofit naming with CODE
  #151    ?         Platform Upper    —                     [Codex] Add collision and recovery coverage f
  #152    ?         Platform Upper    —                     [Codex] Teach harness doctor to validate code
  #153    ?         Platform Upper    —                     [Codex] Add codex skills symlink to harness d
  #154    ?         Platform Upper    —                     [Codex] Document AgentFactory prompt mapping 
  #155    ?         Platform Upper    —                     [Codex] Add project-local .mcp.json awareness
  #156    ?         Platform Upper    —                     [Codex] Document and inventory global ~/.code
  #157    ?         Platform Upper    —                     [Codex] Expose global ~/.codex skills and rul
  #158    ?         Platform Upper    —                     [Codex] Add plugin inventory awareness to Cod
  #159    ?         Platform Upper    —                     [Codex] Define AgentFactory mapping model for
  #160    ?         Platform Upper    —                     [Codex] Expand harness doctor to cover manage
  #161    ?         Platform Upper    —                     [Codex] Broaden Codex retrofit profile to mat
  #162    ?         Platform Upper    —                     [Codex] Reconcile historical harness-init rep
  #163    ?         Platform Upper    —                     [Codex] Add Codex edge-case tests for MCP, .c
  #164    ?         Platform Upper    —                     [Codex] Add live Codex environment verificati
  #165    ?         Platform Upper    —                     [Gemini] Add canonical .gemini/skills support
  #166    ?         Platform Upper    —                     [Gemini] Move Gemini canonical config from co
  #167    ?         Platform Upper    —                     [Gemini] Generate Gemini-native .toml slash c
  #168    ?         Platform Upper    —                     [Gemini] Project mcpServers from .mcp.json in
  #169    ?         Platform Upper    —                     [Gemini] Update harness doctor to validate th
  #170    ?         Platform Upper    —                     [Gemini] Align Gemini retrofit, generation, a
  #171    ?         Platform Upper    —                     [Gemini] Update Gemini docs and tests to the 
  #172    ?         Platform Upper    —                     [Codex] Tracking issue for Codex adapter alig
  #173    ?         Platform Upper    —                     [Gemini] Tracking issue for Gemini adapter al
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

_Generated 2026-05-01 15:24 UTC by `generate-priority-report.py`._
_Run manually: `python3 .ai/scripts/generate-priority-report.py`_
