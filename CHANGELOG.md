# Changelog

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
