# Milestones
<!-- version: 1.10.0 -->

Living traceability matrix for all AgentFactory GitHub issues.
Update this file on every PR merge and release (see git-versioning SKILL.md Step 8.5).

Status values: `done` · `in-progress` · `pending` · `deferred`

---

## Completed

| # | Title | Type | PR | Commit | Tag |
|---|-------|------|----|--------|-----|
| #5 | Add Concurrency Protection for Global Manifests | feature | — | ab05e71 | v2.0.0 |
| #6 | Librarian Core Final Polish | feature | — | — | v2.0.0 |
| #7 | Context-Aware Agent Acknowledgement | feature | — | — | v2.0.0 |
| #9 | Enhance Error Recovery Mechanism | feature | — | — | v2.0.0 |
| #10 | Enhance Librarian Intelligence Layer with AST Parsing | feature | — | 1fc9b7f | v2.0.0 |
| #11 | Implement Integration Tests for CLI Commands | test | — | — | v2.0.0 |
| #12 | Add Safe Rollback Mechanism for retrofit | feature | — | — | v2.0.0 |
| #13 | Enforce Schema Validation for skill-manifest.json | feature | — | — | v2.0.0 |
| #15 | Sync Global Registry on Local Agent Updates | feature | — | e051e38 | v2.0.0 |
| #17 | Agent folder fix | bug-fix | — | — | v2.0.0 |
| #18 | Implement Production-Grade Multi-CLI AI Harness | feature | — | e051e38 | v2.1.0 |
| #20 | Feature: Implement Manifest Librarian | feature | #20 | 3d1871f | v2.0.0 |
| #21 | Feature: Implement Standalone Skill Import | feature | #21 | e051e38 | v2.1.0 |
| #22 | Consolidate AI Context via Symlinks | enhancement | #22 | 764f1df | v2.1.0 |
| #23 | Implement Traceability Matrix for Multi-CLI Agent Imports | feature | #23 | — | v2.1.0 |
| #24 | Fix Multi-CLI Harness Gaps (Symlink Awareness & Config) | bug-fix | #24 | f3dd63c | v2.1.0 |
| #25 | Implement Unified Folder Strategy & Extended Matrix | feature | #25 | 764f1df | v2.1.0 |
| #26 | Fix README inaccuracies | bug-fix | #26 | 21859c9 | v2.1.0 |
| #27 | Add HARNESS_ROOT + CONTEXT_FILE constants | feature | #27 | 9bd40dd | v2.1.0 |
| #28 | Add _ensure_adapter_wiring() | feature | #28 | f3dd63c | v2.1.0 |
| #29 | Add agent-gen init command | feature | #29 | 5bb4d33 | v2.1.0 |
| #30 | Refactor: restructure project under .ai/ | refactor | #30 | 764f1df | v2.1.0 |
| #31 | Update test suite for .ai/ harness paths | test | #31 | — | v2.1.0 |
| #14 | Add Version Management Command (agent-gen bump) | feature | #14 | — | v2.3.0 |
| #32 | Close git-versioning skill gaps | feature | #32 | 079070f | v2.3.0 |
| #35 | Add agent-gen import --from-git pipeline | feature | #35 | 076ffcd | v2.3.0 |
| #4 | diff-visualizer skill | feature | — | — | v2.2.0 |
| #41 | Gemini & Codex adapter configs empty (0 bytes) | harness-fix | #63 | 39f1acd | v2.5.0 |
| #42 | test-agent missing commands/ & scripts/ dirs | harness-fix | #63 | 39f1acd | v2.5.0 |
| #55 | CHANGELOG.md missing version marker | doc-fix | #63 | 39f1acd | v2.5.0 |
| #56 | repo-state.md stale (v2.3.0 → v2.4.2) | doc-fix | #63 | 39f1acd | v2.5.0 |
| #53 | git clone in --from-git missing --quiet flag | cli-bug | #63 | 39f1acd | v2.5.0 |
| #43 | describe --plan accepts non-existent path silently | cli-bug | #63 | 39f1acd | v2.5.0 |
| #45 | Skill version drift silently skips missing frontmatter | audit-bug | #63 | 39f1acd | v2.5.0 |
| #58 | --from-git URL passed unsanitized to subprocess.run | security | #63 | 39f1acd | v2.5.0 |
| #59 | Path inputs used directly for filesystem ops | security | #63 | 39f1acd | v2.5.0 |
| #44 | retrofit should warn when multiple profiles match | enhancement | #63 | 39f1acd | v2.5.0 |
| #54 | Add global --quiet / -q flag to all CLI commands | enhancement | #63 | 39f1acd | v2.5.0 |
| #46 | No test for agent-gen init command | test | #63 | 39f1acd | v2.5.0 |
| #47 | No test for describe --plan option | test | #63 | 39f1acd | v2.5.0 |
| #48 | No test for wrap --out option | test | #63 | 39f1acd | v2.5.0 |
| #49 | No test for import-skill --to . (root project) | test | #63 | 39f1acd | v2.5.0 |
| #50 | No test for import --from-git pipeline | test | #63 | 39f1acd | v2.5.0 |
| #51 | No test for _ensure_adapter_wiring() | test | #63 | 39f1acd | v2.5.0 |
| #52 | No test for _check_repo_state() | test | #63 | 39f1acd | v2.5.0 |
| #57 | Direct commits landing on dev without PR | infra | #63 | 39f1acd | v2.5.0 |
| #60 | No CI workflow — tests not enforced before merge | infra | #63 | 39f1acd | v2.5.0 |
| #61 | No coverage measurement or 80% threshold enforcement | infra | #63 | 39f1acd | v2.5.0 |
| #19 | Implement Token Budget Monitor (harness-doctor) | feature | #63 | 39f1acd | v2.5.0 |
| #62 | Set up production-grade GitHub CI/CD pipeline | feature | #63 | 39f1acd | v2.5.0 |

---

## Roadmap — Production Platform (epic #77)

Business model: freemium SaaS + public agent registry + marketplace.
The CLI stays open-source. The platform is the paid surface.

> **Note (2026-04-21):** The webapp has been extracted to the private
> [agentfactory-webapp](https://github.com/matheusmlopess/agentfactory-webapp) repo.
> Webapp issues (#78, #79, #80, #104, #105) are tracked there going forward.

### Phase 1 — Foundation

| # | Title | Type | Status | Branch | PR | Commit | Tag |
|---|-------|------|--------|--------|----|--------|-----|
| #77 | epic: AgentFactory production platform | epic | pending | — | — | — | — |
| #78 | feat[P1]: webapp scaffold — Vite + React 19 + TS + GitHub Pages | webapp | moved→webapp-repo | — | — | — | — |
| #79 | feat[P1]: harness explorer UI — two-panel file tree + doc pane | webapp | moved→webapp-repo | — | — | — | — |
| #80 | feat[P1]: lifecycle stepper + manifest inspector UI components | webapp | moved→webapp-repo | feature/80-lifecycle-stepper-manifest-inspector | #112 | cf35f7a | — |
| #81 | feat[P1]: public agent registry — browse, search, publish Portable Units | registry | done | feature/81-public-agent-registry | #111 | 17ae0e3 | — |
| #82 | feat[P1]: CLI extensions — agentfactory-gen publish + import --from-registry | cli | done | feature/82-cli-publish-import-registry | #129 | c408abe | — |

### Phase 2 — Auth & Workspaces

| # | Title | Type | Status | Branch | PR | Commit | Tag |
|---|-------|------|--------|--------|----|--------|-----|
| #83 | feat[P2]: GitHub OAuth authentication | platform | done | feature/83-github-oauth-auth-ui | #113 | d0ea86b | — |
| #84 | feat[P2]: private org workspaces + RBAC | platform | pending | — | — | — | — |
| #85 | feat[P2]: Pro tier billing — Stripe seat-based subscription | billing | pending | — | — | — | — |
| #86 | feat[P2]: agentfactory-gen login / logout CLI commands | cli | pending | — | — | — | — |

### Phase 3 — Governance

| # | Title | Type | Status | Branch | PR | Commit | Tag |
|---|-------|------|--------|--------|----|--------|-----|
| #87 | feat[P3]: per-agent audit history dashboard | platform | pending | — | — | — | — |
| #88 | feat[P3]: agent dependency graph visualization | platform | pending | — | — | — | — |
| #89 | feat[P3]: Enterprise compliance export — audit trail + deployment log | platform | pending | — | — | — | — |

### Phase 4 — Marketplace

| # | Title | Type | Status | Branch | PR | Commit | Tag |
|---|-------|------|--------|--------|----|--------|-----|
| #90 | feat[P4]: marketplace — paid agent listings + purchase flow | marketplace | pending | — | — | — | — |
| #91 | feat[P4]: verified agent badge — automated Librarian security scan | registry | pending | — | — | — | — |
| #92 | feat[P4]: publisher revenue share — Stripe Connect payouts | billing | pending | — | — | — | — |

### Webapp track (moved to agentfactory-webapp)

Issues below are tracked in the private webapp repo as of 2026-04-21.

| # | Title | Type | Status |
|---|-------|------|--------|
| #104 | webapp completeness report viewer (static, no API key) | feature | moved→webapp-repo |
| #105 | BYOK live completeness checker in webapp [pro] | feature | moved→webapp-repo |

---

## Superseded / Closed

| # | Title | Note |
|---|-------|------|
| #16 | Project layout GUI React | Superseded by production platform epic #77 |
| #140 | add import --dry-run for pre-registration inspection | Absorbed by #146 (import atomicity overhaul) — already closed |
| #141 | audit runs post-unpack — malicious content registers before detection | Absorbed by #146 (import atomicity overhaul) — already closed |

---

## Completed — FormatSwitch (Codex Skills Gap)

| # | Title | Type | PR | Commit | Tag |
|---|-------|------|----|--------|-----|
| #93 | bug: AGENTS.md symlinks to AgentFactory.md — Codex reads Claude instructions | bug | #97 | 3d83de5 | — |
| #94 | bug: _ensure_adapter_wiring() gives Codex no skills symlink | bug | #97 | 3d83de5 | — |
| #95 | feat: generate Codex-specific AGENTS.md with skill declarations on every sync | enhancement | #97 | 3d83de5 | — |
| #96 | feat: FormatSwitch — per-CLI compiled briefs with adapter activation | feature | #97 | 3d83de5 | — |

---

## Pending

| # | Title | Type | Status | Branch | PR | Commit | Tag |
|---|-------|------|--------|--------|----|--------|-----|
| #79  | harness explorer UI + quality layer (skill completeness, issue tracker, feature workflow SOP) | feature | done | feature/harness-explorer-ui-p1-79 | #99 | eb75c686 | — |
| #100 | pre-commit hook for SKILL.md completeness warning | feature | done | feature/100-skill-completeness-precommit | #106 | cc8f5a8e | — |
| #101 | skill-completeness dedicated CI job | feature | done | feature/101-skill-completeness-ci-job | #107 | 5b8337e | — |
| #102 | integrate completeness gate into adapter-add command | feature | done | feature/102-adapter-add-completeness-gate | #109 | 36c790d | — |
| #103 | per-adapter completeness thresholds in harness config | feature | done | feature/103-per-adapter-completeness-thresholds | #110 | 8e37e66 | — |
| #104 | webapp completeness report viewer (static, no API key) | feature | done | feature/104-webapp-completeness-viewer | #108 | 4f2822b | — |
| #105 | BYOK live completeness checker in webapp [pro] | feature | pending | — | — | — | — |
| #114 | auth backend — FastAPI OAuth server (GitHub + Google), JWT sessions | platform | pending | — | — | — | — |
| #120 | bug: init creates root MD symlinks for primary adapter only | bug | done | fix/120-121-harness-init-gaps | #123 | 47f8e46 | — |
| #121 | bug: update_harness_files skips @skills-registry injection in README when marker absent | bug | done | fix/120-121-harness-init-gaps | #123 | 47f8e46 | — |
| #114 | feat[P2]: auth backend — FastAPI OAuth server + JWT sessions + license validation | platform | done | feature/114-auth-backend | #124 | 39d0e8c | — |
| #125 | feat: AgentFactory.md master brief + preamble injection into all adapter briefs | feature | done | feature/agentfactory-md-master-brief | #125 | c4cd5a2 | v2.8.0 |
| #126 | feat: extend completeness oracle to project-context preamble truncation | feature | done | feature/126-preamble-completeness-oracle | #127 | 70f4fc0 | v2.9.0 |

## Pending (legacy / non-platform)

| # | Title | Type | Status | Branch | PR | Commit | Tag |
|---|-------|------|--------|--------|----|--------|-----|

---

## Open Issues — Wave Execution Plan
<!-- last-reviewed: 2026-05-01 -->

Canonical order derived from dependency analysis. Waves 4 and 5 run in parallel.
Absorption notes: #152+#153→#160 · #165+#166+#169→#170 · #140+#141→#146 (already closed).

### Wave 1 — Foundation bugs

| # | Title | Type | Status |
|---|-------|------|--------|
| #133 | --version flag not defined on root CLI group | bug | pending |
| #132 | audit exits 1 on untracked files without auto-syncing first | bug | pending |
| #135 | --project-root resolves conflict check against CWD, not target root | bug | pending |
| #134 | SKILL.md frontmatter not parsed by import-skill | bug | pending |
| #136 | wrap --out flag undiscoverable; ZIP lands in CWD silently | enhancement | pending |

### Wave 2 — Security

| # | Title | Type | Status |
|---|-------|------|--------|
| #146 | import atomicity + safety overhaul — dry-run, pre-unpack audit, atomic write, rollback | security | pending |
| #143 | --project-root accepts path traversal sequences without validation | security | pending |
| #142 | scripts/ in imported agents execute without sandbox or review gate | security | pending |
| #144 | no checksum or signature verification on imported ZIPs | security | pending |

### Wave 3 — CLI enhancements

| # | Title | Type | Status |
|---|-------|------|--------|
| #137 | add agentfactory-gen status command with per-agent skill listing | enhancement | pending |
| #139 | promote skill-completeness-check and harness-doctor to CLI subcommands | enhancement | pending |
| #148 | add create-skill command with SKILL.md template generator | enhancement | pending |
| #147 | warn when skill version unchanged on re-import | enhancement | pending |
| #149 | add test-skill smoke-test runner | enhancement | pending |
| #138 | add agentfactory-gen upgrade command for in-place agent updates | enhancement | pending |
| #145 | skill creation pipeline: 10 CLI gaps meta-survey (close by ticking resolved GAPs) | enhancement | pending |

### Wave 4 — Codex adapter alignment (parallel with Wave 5)

| # | Title | Type | Status |
|---|-------|------|--------|
| #150 | align Codex retrofit naming with CODEX.md root-file contract | enhancement | pending |
| #161 | broaden Codex retrofit profile to match live harness contract | enhancement | pending |
| #151 | add collision and recovery coverage for existing .codex paths | enhancement | pending |
| #160 | expand harness doctor to cover all managed and observed Codex surfaces *(absorbs #152, #153)* | enhancement | pending |
| #155 | add project-local .mcp.json awareness to Codex mapping and diagnostics | enhancement | pending |
| #163 | add Codex edge-case tests for MCP, .codex collisions, external env visibility | testing | pending |
| #156 | document and inventory global ~/.codex/config.toml as external surface | documentation | pending |
| #157 | expose global ~/.codex skills and rules as external context surfaces | documentation | pending |
| #158 | add plugin inventory awareness to Codex environment reporting | enhancement | pending |
| #159 | define AgentFactory mapping model for plugin-provided Codex tools and MCP | enhancement | pending |
| #162 | reconcile historical harness-init report with current Codex behavior | documentation | pending |
| #164 | add live Codex environment verification study | documentation | pending |
| #154 | document AgentFactory prompt mapping for Codex | documentation | pending |
| #172 | [tracking] Codex adapter alignment epic — close when #150–#164 done | epic | pending |

### Wave 5 — Gemini adapter alignment (parallel with Wave 4)

| # | Title | Type | Status |
|---|-------|------|--------|
| #170 | align Gemini retrofit, generation, and validation contracts *(absorbs #165, #166, #169)* | enhancement | pending |
| #168 | project mcpServers from .mcp.json into .gemini/settings.json | enhancement | pending |
| #167 | generate Gemini-native .toml slash commands from shared command sources | enhancement | pending |
| #171 | update Gemini docs and tests to canonical-plus-bridge model | documentation | pending |
| #173 | [tracking] Gemini adapter alignment epic — close when #165–#171 done | epic | pending |

### Antigravity CLI adapter (2026-07-06)

Gemini CLI was retired 2026-06-18; its successor is Antigravity CLI (`agy`, v1.0.16).
Both are kept as separate adapters — they are distinct tools with different layouts.

| Item | Title | Type | Status | Branch |
|------|-------|------|--------|--------|
| AGY-1 | Add `antigravity` adapter: `.agents/` folder symlink, `.agents/skills` + `.agents/rules` wiring, `mcp_config.json`, AGENTS.md root file | feature | in-progress | feature/antigravity-cli-adapter |
| AGY-2 | Antigravity retrofit profile (`.agents/skills`, `.agents/rules`, `.agents/workflows`) | feature | in-progress | feature/antigravity-cli-adapter |
| AGY-3 | Live probe via `agy -p`; provider-error skips (quota/retirement) for all live agent tests | test | in-progress | feature/antigravity-cli-adapter |

Note: `AGENTS.md` is a shared cross-tool root file — codex owns it at `init`
(registry order), and an explicit `adapter add antigravity` re-points it.
Wave 5 (Gemini adapter alignment) remains valid for the legacy `gemini` adapter.

### Wave 5 Deferred — Open-standard full-compliance (post-Wave 4+5)

These items require the Wave 5 Gemini alignment work to land first.
Tracked against the Agent Skills open standard (agentskills.io, 2026).

| Item | Description | Depends on |
|------|-------------|-----------|
| W5-D1 | Add `.agents/skills/` root-level interop symlink — the cross-agent agreed scan path so Gemini, Copilot, Codex, and Cursor all see AgentFactory skills without adapter-specific paths | Wave 5 merged |
| W5-D2 | Enforce `name` must match parent directory name in `_validate_and_reconcile_skill_manifest` (open standard §name constraint) | Wave 1 + Wave 5 merged |
| W5-D3 | Parse and surface optional fields: `license`, `compatibility`, `allowed-tools` from SKILL.md frontmatter into skill-manifest.json | Wave 5 merged |
| W5-D4 | Full YAML-aware `metadata.version` parsing — replace flat-line parser with a proper nested YAML reader so `metadata:\n  version:` resolves correctly even when other `metadata` sub-keys are present | Wave 5 merged |
