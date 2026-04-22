# Changelog
<!-- version: 2.8.0 -->

## [v2.8.0] - 2026-04-22

### Added
- **AgentFactory.md as full master compiled brief**: `agentfactory-gen brief` now upserts
  `<!-- @commands-start/end -->` and `<!-- @rules-start/end -->` sections into
  `.ai/AgentFactory.md`, giving it the same richness as any per-adapter brief (#125)
- **`## Project Context` injected into every adapter brief**: every compiled brief carries
  the human-written preamble from `.ai/AgentFactory.md`, budget-fitted per adapter
  (claude/gemini: 4 000 chars, codex: 2 000 chars with truncation warning) (#125)
- `context_char_limit` per-adapter config key in `_FORMAT_REGISTRY`
- `_collect_project_context()` — extracts preamble before first `<!-- @` marker, strips H1
- `_fit_context_to_budget()` — paragraph-boundary truncation with warning HTML comment;
  adds completeness-check hint when `AGENTFACTORY_LICENSE_KEY` is set
- `.ai/AgentFactory.md` now listed in the Harness Identity Block shared-context section
- `docs/FEATURE-AGENTFACTORY-MD-BRIEF.md` — complete feature doc with workflow diagrams
  and gap analysis

### Fixed
- `docs/WORKFLOWS.md` diagram 1 was architecturally stale since FormatSwitch (#96):
  showed root symlinks pointing to `AgentFactory.md` instead of compiled briefs (#125)
- README described `AgentFactory.md` as "legacy + sync target" — corrected to "master
  compiled brief"

### Tests
- 7 new tests in `test_librarian_lifecycle.py` (203 total): context injection,
  H1/registry stripping, missing-AF.md graceful compile, codex truncation,
  claude no-truncation, AgentFactory.md rules+commands upsert, harness identity reference

---

## [v2.7.0] - 2026-04-22

### Added
- **FastAPI auth backend** (#114): GitHub OAuth flow, JWT httpOnly cookie sessions,
  SQLite default (swappable to PostgreSQL via `DATABASE_URL` env var), license key
  validation endpoint
- `src/agent_gen/api/` — new module: `main.py`, `db.py`, `jwt_utils.py`, `models.py`,
  `deps.py`, `routers/auth.py`, `routers/license.py`
- `agentfactory-api` CLI entry point (uvicorn-backed dev server)
- `api` extras in `pyproject.toml`: `fastapi`, `uvicorn[standard]`, `python-jose`, `httpx`, `pydantic`
- `docker-compose.yml` + `Dockerfile.api` — one-command full-stack local dev (API + PostgreSQL)
- `.env.example` — documents all environment variables
- `api/openapi.json` — committed OpenAPI spec (webapp's authoritative type source)
- `docs/MULTI-REPO-WORKFLOW.md` — two-repo development protocol, type generation, wave map

### Tests
- `src/tests/test_api_auth.py` — 15 tests: JWT, license validation, /auth/me, /auth/logout, /health

---

## [v2.6.0] - 2026-04-22

### Fixed
- `agentfactory-gen init` now creates root symlinks for **all** registered adapters, not
  only the primary one (#120). Previously `init --primary codex` would create `AGENTS.md`
  and `CODEX.md` but leave `CLAUDE.md` and `GEMINI.md` absent.
- `update_harness_files()` now injects `## Available Skills` into files that lack the
  `<!-- @skills-registry:start -->` marker (#121). Previously the injection was silently
  skipped, leaving READMEs without a skills section on first run.

### Tests
- Updated 5 integration stress tests that encoded the old single-adapter root-file behavior
- Added 2 lifecycle tests for skills-registry injection: marker-absent and marker-present

---

## [v2.5.2] - 2026-04-14

### Fixed
- Codex adapter init and `adapter add codex` now default to `model = "gpt-5.4"` instead of the unsupported `o4-mini`
- Compiled Claude, Codex, and Gemini briefs now render actual behavior-rule summaries instead of placeholder version markers
- `diff-visualizer` skill metadata was shortened so Codex can load it without rejecting the `SKILL.md` description field

### Added
- Shared `skill-briefing` rule to keep skill `description` and `triggers` metadata brief-safe for compiled briefs

### Tests
- Added coverage for generated Codex config defaults, Codex brief metadata rendering, and brief-rule propagation across adapters

## [v0.3.1] - 2026-04-13

### Security
- ZIP Slip: replaced `ZipFile.extractall()` with `_safe_extract()` guard in librarian + CLI — blocks path traversal via crafted ZIP entries (S1)
- Prompt injection: all agent names/descriptions sanitized via `_sanitize_for_markdown()` before being written to AI-readable markdown files (S2, S5)
- Path traversal: `_assert_within_root()` rewritten to use `Path.is_relative_to()` — fixes `startswith` prefix-bypass (S3)
- Agent name from URL sanitized with `re.sub(r"[^\w\-]", "-", name)` before use in paths and manifests (S4)
- Dependency versions capped: `click>=8.1,<9.0`, `filelock>=3.13.0,<4.0` (S6)
- `softprops/action-gh-release` pinned to commit SHA (S7)
- `awk` pattern in `release.yml` now escapes `github.ref_name` before use (S8)

### Fixed
- CLI entry point renamed `agent-gen` → `agentfactory-gen` to match the PyPI package name (S0)
- All `agent-gen` references in README and docs updated to `agentfactory-gen`

### Tests
- 78 tests passing, 85% coverage
- Added `test_security.py` with 13 security regression tests
- Added zip-slip tests to `test_librarian_lifecycle.py`
- Added 14 error-path tests to `test_cli.py` (duplicate deploy, uninstall abort, audit, import errors, quiet flag, etc.)

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
