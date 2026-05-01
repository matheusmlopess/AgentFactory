# Study: Codex Init Scenarios
<!-- version: 1.0.0 -->

This study focuses on what happens when AgentFactory initializes Codex support in
different project states and adapter combinations.

## Scope

Covered sources:
- `src/agent_gen/cli.py`
- `src/agent_gen/librarian.py`
- `src/tests/test_cli.py`
- `src/tests/test_cli_swap_scenarios.py`
- `src/tests/test_integration_stress.py`
- `src/tests/test_librarian_lifecycle.py`
- `docs/TEST-REPORT-HARNESS-INIT.md`

Covered behaviors:
- `agentfactory-gen init`
- `agentfactory-gen init --primary <adapter>`
- `agentfactory-gen adapter add codex`
- repeated init/add operations
- interaction with existing project files relevant to Codex

## Init Chronology

```text
┌─ init_project()
│
├─ create .ai/ directory tree
├─ scaffold .ai/memory/milestones.md
├─ scaffold .ai/AgentFactory.md
├─ scaffold .ai/agent-manifest.json
├─ write adapter config defaults
├─ _ensure_adapter_wiring()
│  └─ codex gets:
│     ├─ skills  -> ../../skills
│     └─ prompts -> ../../commands
├─ _compile_adapter_briefs()
│  └─ codex brief.md rendered
├─ create root brief symlinks
│  ├─ AGENTS.md
│  └─ CODEX.md
└─ create folder symlink
   └─ .codex -> .ai/adapters/codex
```

## Scenario Status Legend

- `Works`: current code and tests support the scenario cleanly
- `Partial`: some outcome works, but the Codex mapping story is incomplete
- `Missing`: no current support or clear evidence
- `Historical`: documented old failure that appears fixed in current code/tests
- `Unverified`: reasonable scenario, but no direct current test evidence

## Scenario Matrix

```text
┌────┬───────────────────────────────────────────────┬────────────┬──────────────────────────────────────────────┐
│ ID │ Scenario                                      │ Status     │ Notes                                        │
├────┼───────────────────────────────────────────────┼────────────┼──────────────────────────────────────────────┤
│ S1 │ Fresh repo, default init                      │ Works      │ Root links, .codex, config, prompts, skills. │
│ S2 │ Fresh repo, --primary codex                   │ Works      │ Codex brief becomes primary target.          │
│ S3 │ Fresh repo, --primary gemini or claude        │ Works      │ Codex links still created after init.        │
│ S4 │ Existing repo, no .ai/                        │ Works      │ Historical report confirms real-world use.   │
│ S5 │ Re-run init on already initialized repo       │ Works      │ Existing artifacts are skipped, not clobbered.│
│ S6 │ Add codex after non-codex init                │ Works      │ Brief, config, root links, wiring created.   │
│ S7 │ Re-run adapter add codex                      │ Works      │ Config preserved; wiring remains valid.      │
│ S8 │ Existing regular-file AGENTS.md               │ Works      │ AF does not clobber user file.               │
│ S9 │ Existing user-edited codex config.toml        │ Works      │ Adapter add is idempotent.                   │
│ S10│ Existing .mcp.json                            │ Partial    │ Coexists, but not modeled or validated.      │
│ S11│ Existing non-symlink .codex directory         │ Unverified │ Code skips existing path; no direct test.    │
│ S12│ Existing partial .ai/adapters/codex state     │ Partial    │ Wiring can fill gaps; full matrix untested.  │
│ S13│ Global ~/.codex environment present           │ Partial    │ Runtime relevant, but outside harness logic. │
│ S14│ Plugin-provided codex capabilities installed  │ Missing    │ No init-time inventory or reporting.         │
└────┴───────────────────────────────────────────────┴────────────┴──────────────────────────────────────────────┘
```

## Adapter Artifact Matrix After Init

Expected current Codex-visible state after successful `init`:

```text
┌────────────────────────────────────┬──────────────────────────────┬────────────────────────────────────────┐
│ Artifact                           │ Current Result               │ Evidence                                │
├────────────────────────────────────┼──────────────────────────────┼────────────────────────────────────────┤
│ .ai/adapters/codex/                │ Created                      │ cli.py init_project                      │
│ .ai/adapters/codex/brief.md        │ Compiled                     │ init + integration tests                 │
│ .ai/adapters/codex/config.toml     │ Created if absent            │ cli.py + test_cli.py                     │
│ .ai/adapters/codex/skills          │ Symlink to ../../skills      │ integration and lifecycle tests          │
│ .ai/adapters/codex/prompts         │ Symlink to ../../commands    │ integration and lifecycle tests          │
│ .codex                             │ Symlink to .ai/adapters/codex│ cli.py init_project                      │
│ AGENTS.md                          │ Symlink to codex brief       │ test_cli.py / integration stress         │
│ CODEX.md                           │ Symlink to codex brief       │ test_cli.py / integration stress         │
│ .mcp.json                          │ Left untouched               │ observed local behavior                  │
│ ~/.codex/config.toml               │ Left untouched               │ outside project ownership                │
└────────────────────────────────────┴──────────────────────────────┴────────────────────────────────────────┘
```

## Detailed Scenario Notes

### S1. Fresh repo, default init

Current result:
- works
- codex adapter assets are created even when primary is `claude`

Evidence:
- `test_init_creates_all_adapter_root_symlinks`
- `test_codex_skills_symlink_fixed`
- `test_codex_prompts_and_skills_wired`

Codex outcome:
- `AGENTS.md` and `CODEX.md` exist
- `.codex` exists
- `config.toml` exists
- prompt and skill links exist

### S2. Fresh repo, `--primary codex`

Current result:
- works
- codex is the selected primary, but all adapter root files still exist

Evidence:
- `test_codex_primary_sets_agents_md`
- `test_codex_primary_sets_codex_md`
- `test_codex_primary_creates_all_root_files`

### S3. Fresh repo, non-codex primary

Current result:
- works
- codex is still fully wired because init compiles all adapter briefs and creates all root links

Evidence:
- `test_init_creates_all_adapter_root_symlinks`
- `test_gemini_primary_creates_all_root_files`

### S4. Existing non-AgentFactory repo

Current result:
- works in documented real-world use
- historical report shows successful adoption into a populated repo

Important nuance:
- the historical report contains outdated root-link gap observations
- current code path now loops over all adapters for root links

### S5. Re-run init

Current result:
- works
- existing files and links are skipped rather than overwritten

Evidence:
- direct code behavior in `init_project()`
- every artifact write is guarded by existence checks

Remaining gap:
- no dedicated matrix-style test enumerates every Codex artifact on second run

### S6. Add codex after non-codex init

Current result:
- works

Evidence:
- `test_adapter_add_creates_dir_and_brief`
- `test_codex_add_creates_root_symlinks`
- `test_codex_add_creates_skills_symlink`
- `test_codex_add_writes_config`

### S7. Re-run `adapter add codex`

Current result:
- works

Evidence:
- `test_adapter_add_idempotent`

Outcome:
- existing `config.toml` is preserved
- links remain valid
- brief can be refreshed

### S8. Existing regular-file `AGENTS.md`

Current result:
- works
- AgentFactory does not clobber a user-owned real file

Evidence:
- `test_adapter_add_skips_non_symlink_root_file`

Tradeoff:
- local project may now diverge from ideal Codex root-link wiring
- this is safer for user data, but deserves diagnostics

### S9. Existing user-edited codex config

Current result:
- works

Evidence:
- `test_adapter_add_idempotent`

### S10. Existing `.mcp.json`

Current result:
- partial

Observed behavior:
- file can exist at repo root
- AgentFactory leaves it alone
- no Codex-specific study or diagnostics currently explain what it means

Why this matters:
- `.mcp.json` is a meaningful Codex-local discovery surface
- current harness contract ignores it

### S11. Existing non-symlink `.codex` directory

Current result:
- unverified

Code reading suggests:
- `init_project()` and adapter wiring skip existing paths rather than replacing them
- that protects user data
- it may also leave the project in a mixed or unsupported shape

Needed follow-up:
- explicit test covering real directory, broken link, and custom link targets

### S12. Existing partial codex adapter state

Current result:
- partial

Observed behavior:
- `_ensure_adapter_wiring()` can create missing links in existing adapter dirs
- there is no dedicated end-to-end scenario covering multiple missing/present combinations

### S13. Global `~/.codex` environment already populated

Current result:
- partial

Reason:
- Codex will still use the global environment
- AgentFactory init does not inventory or report it

### S14. Plugins installed in global Codex home

Current result:
- missing from init story

Reason:
- plugins materially affect Codex capability surface
- current harness init and diagnostics do not expose that fact

## Works / Does Not Work Summary

```text
┌───────────────────────────────────────┬──────────┬─────────────────────────────────────────────┐
│ Area                                  │ Works?   │ Comment                                     │
├───────────────────────────────────────┼──────────┼─────────────────────────────────────────────┤
│ Codex root file creation              │ Yes      │ Current tests confirm AGENTS.md + CODEX.md. │
│ Codex folder link creation            │ Yes      │ `.codex` is created by init.                │
│ Codex prompts/skills wiring           │ Yes      │ Explicit symlink tests exist.               │
│ Codex config creation                 │ Yes      │ Default file written if absent.             │
│ Config preservation on rerun          │ Yes      │ Existing edits are preserved.               │
│ Respect existing AGENTS.md file       │ Yes      │ No clobber behavior is tested.              │
│ `.mcp.json` mapping/documentation     │ No       │ Surface exists but is not first-class.      │
│ Global `~/.codex` awareness           │ No       │ No inventory or reporting contract.         │
│ Plugin-aware init/diagnostics         │ No       │ Not represented in current harness.         │
│ Non-symlink `.codex` collision story  │ Unknown  │ Safe skip likely, but not directly tested.  │
└───────────────────────────────────────┴──────────┴─────────────────────────────────────────────┘
```

## Historical Versus Current Truth

`docs/TEST-REPORT-HARNESS-INIT.md` is still useful but must be read carefully:

- historical claim: non-primary root files were missing
- current truth: tests now confirm all root files are created on init

The report should therefore be treated as:
- good evidence of initialization flow in a real repo
- outdated evidence for root-link gaps

## Follow-up Testing Targets

Most important unverified Codex init scenarios:

1. existing real `.codex/` directory
2. existing broken `.codex` symlink
3. existing `.mcp.json` with declared MCP servers
4. init in repo with custom `~/.codex` global config and plugins present
5. partial adapter recovery matrix for missing `brief.md`, `config.toml`, `skills`, `prompts`

## Related Studies

- `docs/STUDY-CODEX-PROJECT-MAPPING.md`
- `docs/STUDY-CODEX-GAP-MATRIX.md`
- `docs/TEST-REPORT-HARNESS-INIT.md`
