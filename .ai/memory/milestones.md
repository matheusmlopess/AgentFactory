# Milestones
<!-- version: 1.6.4 -->

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

### Phase 1 — Foundation

| # | Title | Type | Status | Branch | PR | Commit | Tag |
|---|-------|------|--------|--------|----|--------|-----|
| #77 | epic: AgentFactory production platform | epic | pending | — | — | — | — |
| #78 | feat[P1]: webapp scaffold — Vite + React 19 + TS + GitHub Pages | webapp | in-progress | feature/webapp-scaffold-p1-78 | — | — | — |
| #79 | feat[P1]: harness explorer UI — two-panel file tree + doc pane | webapp | in-progress | feature/harness-explorer-p1-79 | — | — | — |
| #80 | feat[P1]: lifecycle stepper + manifest inspector UI components | webapp | pending | — | — | — | — |
| #81 | feat[P1]: public agent registry — browse, search, publish Portable Units | registry | pending | — | — | — | — |
| #82 | feat[P1]: CLI extensions — agentfactory-gen publish + import --from-registry | cli | pending | — | — | — | — |

### Phase 2 — Auth & Workspaces

| # | Title | Type | Status | Branch | PR | Commit | Tag |
|---|-------|------|--------|--------|----|--------|-----|
| #83 | feat[P2]: GitHub OAuth authentication | platform | pending | — | — | — | — |
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

---

## Superseded / Closed

| # | Title | Note |
|---|-------|------|
| #16 | Project layout GUI React | Superseded by production platform epic #77 |

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
| #100 | pre-commit hook for SKILL.md completeness warning | feature | pending | — | — | — | — |
| #101 | skill-completeness dedicated CI job | feature | pending | — | — | — | — |
| #102 | integrate completeness gate into adapter-add command | feature | pending | — | — | — | — |
| #103 | per-adapter completeness thresholds in harness config | feature | pending | — | — | — | — |
| #104 | webapp completeness report viewer (static, no API key) | feature | pending | — | — | — | — |
| #105 | BYOK live completeness checker in webapp [pro] | feature | pending | — | — | — | — |

## Pending (legacy / non-platform)

| # | Title | Type | Status | Branch | PR | Commit | Tag |
|---|-------|------|--------|--------|----|--------|-----|
