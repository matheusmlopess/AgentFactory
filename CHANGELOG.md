# Changelog
<!-- version: 2.5.0 -->

## [v2.5.0] - 2026-04-13

### Added
- **Traceability matrix** — `.ai/memory/milestones.md` living matrix tracking all GitHub issues (open + closed) with branch/PR/commit/tag columns
- **Milestones rule** — `.ai/rules/milestones.md` enforcing matrix maintenance on every PR merge and release
- **git-versioning skill Step 8.5** — mandatory step to update `milestones.md` after every merged PR or release
- **CI pipeline** — `.github/workflows/ci.yml`: ruff lint gate + pytest matrix (Python 3.11 + 3.12) + `--cov-fail-under=80`; branch protection on `dev` requires CI to pass before merge
- **CD pipeline** — `.github/workflows/release.yml`: build wheel/sdist → GitHub Release (notes from CHANGELOG) → PyPI publish via OIDC trusted publishing (no stored secrets)
- **Harness Doctor** — `.ai/scripts/harness-doctor.sh`: full health check script with exit codes 0/1/2 and `--ci` machine-readable mode
- **Global `--quiet`/`-q` flag** — suppresses all informational output across every CLI command (#54)
- **`milestones.md` scaffold on `agent-gen init`** — every new project starts with a traceability matrix (#B)
- **`docs/CICD-WORKFLOW.md`** — full CI/CD concept explainer and pipeline reference

### Fixed
- `git clone` in `--from-git` now passes `--quiet` flag (#53)
- `describe --plan` warns when the given path does not exist on disk (#43)
- Skill version drift audit now emits a warning when `SKILL.md` has no version frontmatter instead of silently skipping (#45)
- Gemini and Codex adapter configs were 0 bytes; now have proper stubs (#41)
- `test-agent` was missing `commands/` and `scripts/` directories (#42)

### Security
- `--from-git` URL validated against allowed schemes (`https://`, `http://`, `git@`, `ssh://`, `git://`) before being passed to subprocess (#58)
- `_assert_within_root()` path traversal guard applied to all filesystem operations on user-supplied paths (#59)

### Enhanced
- `retrofit` warns when multiple CLI profiles are detected for the same repo (#44)
- `CHANGELOG.md` now carries `<!-- version: X.Y.Z -->` marker (#55)
- `repo-state.md` updated to v2.4.2 with full version history (#56)

### Tests
- 14 new tests covering: `init` dir tree + idempotence, `describe --plan`, `wrap --out`, `import-skill --to .`, `import --from-git` (mocked), `_ensure_adapter_wiring`, `_check_repo_state`, skill version drift (#46–#52)

### Infrastructure
- `pyproject.toml` dev extras: added `pytest-cov>=5` and `ruff>=0.4`
- Coverage config: `branch = true`, `fail_under = 80`, `show_missing = true`
- README rewritten with 8 Mermaid workflow diagrams covering every major pipeline

---

## [v2.4.2] - 2026-04-09

### Fixed
- Removed stale `agent_gen.egg-info/` artifact left over from pre-src-layout migration
- Fixed `test-agent` registry description (was "Manual Description")

---

## [v2.4.1] - 2026-04-09

### Changed
- Relocated `tests/` → `src/tests/` to match standard Python src layout
- `pyproject.toml` `testpaths` updated to `["src/tests"]`

---

## [v2.4.0] - 2026-04-09

### Changed
- Moved `agent_gen/` → `src/agent_gen/` (standard Python src layout)
- `pyproject.toml` `packages.find.where = ["src"]`
- Removed stale root-level dirs: `plans/`, `mnt/`, `scripts/`, `issues/`
- Relocated `SPEC.md` → `docs/SPEC.md`
- Updated README with accurate layout diagram, CLI reference, and `docs/SPEC.md` link

---

## [v2.3.2] - 2026-04-09

### Changed
- Renamed single source of truth from `.ai/.CLAUDE.md` → `.ai/AgentFactory.md`
- `CONTEXT_FILE` constant updated; all four root symlinks rewired

---

## [v2.3.1] - 2026-04-09

### Changed
- **git-versioning v1.2.1:** `gh release create` is now mandatory in Step 8 — documented as an atomic step alongside `git tag` and `git push`

---

## [v2.3.0] - 2026-04-09

### Added
- **`agent-gen import --from-git <url>`:** Clone any git repo, auto-retrofit it, extract descriptions from README/CLAUDE.md, generate `skill-manifest.json` stubs, and register — all in one command
- `Librarian._extract_source_context()` — reads source CLAUDE.md and sub-agent markdowns before retrofit to populate intelligent descriptions
- `Librarian._auto_stub_skill_manifests()` — promotes flat sub-agent `.md` files to subdirectories with `skill-manifest.json` stubs

---

## [v2.2.0] - 2026-04-09

### Added
- **git-versioning v1.2.0:** Session Branch Gate (Step 0.5) — blocks all work if on the default branch; guides user to create a feature branch or stash dirty changes

---

## [v2.1.1] - 2026-04-09

### Fixed
- Harness cleanup: removed empty/stub files, fixed stale paths, added missing `skill-manifest.json` files
- Fixed `test-agent/repo-state.md` pointing to wrong repo

### Added
- **Audit gap detection** in `Librarian.audit()`:
  - Gap 1: detect `skill-manifest.json` ↔ `SKILL.md` version drift
  - Gap 2: warn when latest git tag is absent from `repo-state.md`
  - Gap 3: warn when `repo-state.md` remote URL doesn't match `git remote origin`

---

## [v2.1.0] - 2026-04-09

### Added
- `agent-gen init` command — scaffolds full `.ai/` structure, `AgentFactory.md`, root symlinks, adapter wiring
- `Librarian._ensure_adapter_wiring()` — idempotently creates missing adapter symlinks (claude: commands→, skills→; gemini: tools→; codex: prompts→)
- `HARNESS_ROOT` and `CONTEXT_FILE` constants in `librarian.py`

### Changed
- All harness content consolidated under `.ai/` (was scattered at project root)
- `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `CODEX.md` all symlink to a single source of truth
- `update_harness_files()` targets simplified to single context file

---

## [v2.0.0] - 2026-04-08

### Added
- **Unified AI Harness:** Symlink-based adapter pattern — Claude, Codex, and Gemini share a single source of truth via `.ai/`
- **Standalone Skill Import:** `agent-gen import-skill <path> --to <agent>`
- **E2E Integration Tests:** `tests/test_cli.py` with `click.testing.CliRunner`
- **Canonical Retrofit Parsing:** Auto-detects and maps Claude Code CLI, Codex CLI, and Gemini CLI folder structures

### Changed
- Librarian `update_harness_files` is symlink-aware — no accidental duplication of root symlinks

### Fixed
- Deeply nested directories no longer crash `shutil.move` during `retrofit`
- Ephemeral harness paths added to `.gitignore`
