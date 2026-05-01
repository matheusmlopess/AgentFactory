# Study: Codex Gap Matrix
<!-- version: 1.0.0 -->

This matrix is the issue-splitting view of Codex support in AgentFactory.

Use it to create focused GitHub issues without re-deriving the problem statement.

## Status Scale

- `Works`: capability is implemented and evidenced
- `Partial`: some behavior exists, but mapping, diagnostics, or contract is incomplete
- `Missing`: no first-class support
- `Unverified`: likely behavior exists, but evidence is missing

## Capability Matrix

```text
┌──────────────────────────────────┬──────────┬────────────────────────────────────────────────────────────────────────────┬──────────┐
│ Capability                       │ Works?   │ Gap                                                                        │ Priority │
├──────────────────────────────────┼──────────┼────────────────────────────────────────────────────────────────────────────┼──────────┤
│ Root-file discovery              │ Works    │ Retrofit/profile naming still mismatched with live contract.               │ High     │
│ `.codex` adapter folder wiring   │ Works    │ Collision and recovery scenarios need explicit diagnostics and tests.      │ Medium   │
│ Codex config creation            │ Works    │ Doctor does not validate config presence or shape.                         │ Medium   │
│ Shared skill exposure            │ Works    │ Doctor/docs do not treat it as a first-class codex check.                  │ Medium   │
│ Shared prompt exposure           │ Works    │ Prompt mapping exists, but prompt semantics are under-documented.          │ Medium   │
│ Project-local MCP discovery      │ Partial  │ `.mcp.json` not included in formal Codex mapping contract.                 │ High     │
│ Global Codex config awareness    │ Partial  │ `~/.codex/config.toml` not surfaced as an observed external dependency.    │ Medium   │
│ Global skills/rules awareness    │ Partial  │ External skill/rule surfaces exist but are absent from harness mapping.    │ Medium   │
│ Plugin inventory awareness       │ Partial  │ Installed plugins are visible externally, but not inventoried by AF.       │ High     │
│ Plugin MCP/app/tool mapping      │ Missing  │ No explicit model for plugin-provided tools and capabilities.              │ High     │
│ Diagnostics coverage             │ Partial  │ `harness-doctor.sh` checks codex prompts only.                             │ High     │
│ Retrofit/import mapping          │ Partial  │ `codex.md` naming mismatch and narrow profile coverage.                    │ High     │
│ Docs consistency                 │ Partial  │ Some docs reflect historical gaps instead of current behavior.             │ Medium   │
│ Test coverage completeness       │ Partial  │ Missing collision and environment-aware scenarios.                         │ High     │
│ Live verification coverage       │ Partial  │ Real-world init report exists, but global/plugin surfaces are untracked.   │ Medium   │
└──────────────────────────────────┴──────────┴────────────────────────────────────────────────────────────────────────────┴──────────┘
```

## Issue-Ready Rows

### 1. Root-file discovery and naming consistency

- Current State: init and adapter-add create `AGENTS.md` and `CODEX.md`; tests cover this.
- Expected State: all Codex-related code paths use the same naming contract.
- Works?: `Works`
- Gap: `CONVERSION_PROFILES["codex"]` still maps `codex.md`, while active adapter wiring uses `CODEX.md`.
- Primary Evidence: `src/agent_gen/librarian.py`, Codex format registry, retrofit profile.
- Touchpoints: `src/agent_gen/librarian.py`, retrofit tests, docs.
- Suggested GH Issue: `Align Codex retrofit naming with CODEX.md root-file contract`
- Acceptance Criteria:
  - conversion profile uses the same root-file conventions as active adapter wiring
  - tests cover retrofit and init with identical naming expectations
  - docs describe one canonical naming scheme
- Priority: `High`

### 2. `.codex` adapter folder wiring

- Current State: init creates `.codex -> .ai/adapters/codex`.
- Expected State: collision cases and partial recovery are well-defined and tested.
- Works?: `Works`
- Gap: no direct evidence for existing real `.codex/`, broken links, or custom link targets.
- Primary Evidence: `src/agent_gen/cli.py`
- Touchpoints: `cli.py`, future diagnostics, tests.
- Suggested GH Issue: `Add collision and recovery coverage for existing .codex paths`
- Acceptance Criteria:
  - tests cover existing directory, symlink, and broken symlink scenarios
  - diagnostics explain when `.codex` is present but not AgentFactory-managed
- Priority: `Medium`

### 3. Codex config creation and validation

- Current State: `config.toml` is scaffolded and preserved on rerun.
- Expected State: diagnostics also verify presence and basic integrity.
- Works?: `Works`
- Gap: doctor does not validate Codex config at all.
- Primary Evidence: `src/agent_gen/cli.py`, `src/tests/test_cli.py`
- Touchpoints: `harness-doctor.sh`, docs, tests.
- Suggested GH Issue: `Teach harness doctor to validate codex config.toml presence`
- Acceptance Criteria:
  - doctor reports missing `config.toml`
  - doctor distinguishes missing from user-edited custom content
- Priority: `Medium`

### 4. Shared skill exposure

- Current State: `skills -> ../../skills` exists and is tested.
- Expected State: docs and diagnostics treat this as a core Codex capability path.
- Works?: `Works`
- Gap: doctor script does not explicitly validate Codex skills link.
- Primary Evidence: `_FORMAT_REGISTRY`, integration tests.
- Touchpoints: `harness-doctor.sh`, docs.
- Suggested GH Issue: `Add codex skills symlink to harness doctor coverage`
- Acceptance Criteria:
  - doctor checks `.ai/adapters/codex/skills`
  - docs list it as managed Codex surface
- Priority: `Medium`

### 5. Shared prompt exposure

- Current State: `prompts -> ../../commands` exists and is tested.
- Expected State: prompt exposure is documented as AgentFactory’s Codex command mapping story.
- Works?: `Works`
- Gap: current docs mention prompts lightly but do not fully explain prompt versus command semantics.
- Primary Evidence: `_FORMAT_REGISTRY`, integration tests, README.
- Touchpoints: README, study docs, adapter docs.
- Suggested GH Issue: `Document AgentFactory prompt mapping for Codex`
- Acceptance Criteria:
  - docs explain why Codex uses prompts rather than a Commands section
  - docs point from shared `.ai/commands` to `.codex/prompts`
- Priority: `Medium`

### 6. Project-local MCP discovery

- Current State: `.mcp.json` can exist in the project root, but AgentFactory ignores it.
- Expected State: AgentFactory documents and reports `.mcp.json` as a relevant local Codex surface.
- Works?: `Partial`
- Gap: no formal contract, no diagnostics, no tests.
- Primary Evidence: root `.mcp.json`, local environment.
- Touchpoints: docs, doctor, possibly audit tooling.
- Suggested GH Issue: `Add project-local .mcp.json awareness to Codex mapping and diagnostics`
- Acceptance Criteria:
  - docs classify `.mcp.json` as observed local surface
  - diagnostics report presence/absence
  - tests cover repo with `.mcp.json`
- Priority: `High`

### 7. Global Codex config awareness

- Current State: `~/.codex/config.toml` exists externally and affects runtime.
- Expected State: AgentFactory can at least document and optionally inventory this dependency.
- Works?: `Partial`
- Gap: no formal awareness in current harness docs or tooling.
- Primary Evidence: observed user-global Codex home.
- Touchpoints: study docs, future environment doctor.
- Suggested GH Issue: `Document and inventory global ~/.codex/config.toml as external Codex surface`
- Acceptance Criteria:
  - docs classify the path correctly
  - any future checks are read-only and opt-in
- Priority: `Medium`

### 8. Global skills and rules awareness

- Current State: external skills and rules exist under `~/.codex/`.
- Expected State: AgentFactory clearly distinguishes global Codex surfaces from project harness surfaces.
- Works?: `Partial`
- Gap: no visible contract or reporting.
- Primary Evidence: observed global layout.
- Touchpoints: docs, future diagnostics.
- Suggested GH Issue: `Expose global ~/.codex skills and rules as external context surfaces`
- Acceptance Criteria:
  - docs identify these as external
  - tooling, if added, does not mutate them
- Priority: `Medium`

### 9. Plugin inventory awareness

- Current State: installed plugins exist under `~/.codex/plugins/cache/...`.
- Expected State: AgentFactory recognizes plugin presence when explaining Codex capability surface.
- Works?: `Partial`
- Gap: plugins are effectively invisible in current harness modeling.
- Primary Evidence: observed global plugin cache.
- Touchpoints: docs, future environment reporting.
- Suggested GH Issue: `Add plugin inventory awareness to Codex environment reporting`
- Acceptance Criteria:
  - docs describe plugin cache and plugin-provided capabilities
  - optional diagnostics can list installed plugin identities
- Priority: `High`

### 10. Plugin MCP / app / tool mapping

- Current State: plugin-provided capabilities are available to Codex at runtime, but not represented in AgentFactory mapping.
- Expected State: AgentFactory can explain that capability surface distinctly from harness-managed assets.
- Works?: `Missing`
- Gap: no explicit model at all.
- Primary Evidence: installed plugin layout and runtime behavior.
- Touchpoints: docs, future plugin-aware mapping model.
- Suggested GH Issue: `Define AgentFactory mapping model for plugin-provided Codex tools and MCP surfaces`
- Acceptance Criteria:
  - docs define plugin-provided surface class
  - issue scope excludes mutating global plugin installs by default
- Priority: `High`

### 11. Diagnostics coverage

- Current State: `harness-doctor.sh` checks `adapters/codex/prompts` only.
- Expected State: all AgentFactory-managed Codex surfaces are validated, with external surfaces reported separately.
- Works?: `Partial`
- Gap: large portions of Codex support are unvalidated.
- Primary Evidence: `.ai/scripts/harness-doctor.sh`
- Touchpoints: doctor script, docs, tests.
- Suggested GH Issue: `Expand harness doctor to cover managed and observed Codex surfaces`
- Acceptance Criteria:
  - doctor checks root files, config, prompts, skills, `.codex`
  - doctor reports `.mcp.json` as observed local surface
  - external surfaces are informative-only
- Priority: `High`

### 12. Retrofit and import mapping

- Current State: retrofit detects Codex layouts, but the mapping is narrower than current harness behavior.
- Expected State: retrofit/import and init share a coherent Codex model.
- Works?: `Partial`
- Gap: naming mismatch and incomplete surface coverage.
- Primary Evidence: `CONVERSION_PROFILES["codex"]`, retrofit tests.
- Touchpoints: `librarian.py`, `test_cli.py`, docs.
- Suggested GH Issue: `Broaden Codex retrofit profile to match live harness contract`
- Acceptance Criteria:
  - retrofit handles current root-file conventions
  - docs align retrofit story with init story
- Priority: `High`

### 13. Docs consistency

- Current State: current code and tests say one thing; an older report still shows obsolete gaps.
- Expected State: docs clearly label historical evidence versus current behavior.
- Works?: `Partial`
- Gap: stale historical interpretation can mislead future issue triage.
- Primary Evidence: `docs/TEST-REPORT-HARNESS-INIT.md`
- Touchpoints: study docs, README, report cross-links.
- Suggested GH Issue: `Reconcile historical harness-init report with current Codex behavior`
- Acceptance Criteria:
  - docs label outdated findings explicitly
  - no current-facing doc repeats fixed gaps as active issues
- Priority: `Medium`

### 14. Test coverage completeness

- Current State: core init and add flows are well covered; collision and environment scenarios are not.
- Expected State: coverage includes edge-case Codex discovery states.
- Works?: `Partial`
- Gap: no direct tests for `.mcp.json`, existing `.codex/`, global config/plugin visibility.
- Primary Evidence: current test suite inventory.
- Touchpoints: `src/tests/*`
- Suggested GH Issue: `Add Codex edge-case tests for MCP, .codex collisions, and external environment visibility`
- Acceptance Criteria:
  - new tests cover those scenarios
  - docs update scenario matrix accordingly
- Priority: `High`

### 15. Live verification coverage

- Current State: one real-world init report exists; it is valuable but partially historical.
- Expected State: live studies include current global/plugin-aware observations.
- Works?: `Partial`
- Gap: no current live evidence for global `~/.codex` and plugin surfaces.
- Primary Evidence: `docs/TEST-REPORT-HARNESS-INIT.md`
- Touchpoints: future study docs and optional live scripts.
- Suggested GH Issue: `Add live Codex environment verification study for global config and plugin surfaces`
- Acceptance Criteria:
  - live study is read-only
  - captures current environment-dependent Codex surfaces
- Priority: `Medium`

## Related Studies

- `docs/STUDY-CODEX-PROJECT-MAPPING.md`
- `docs/STUDY-CODEX-INIT-SCENARIOS.md`
