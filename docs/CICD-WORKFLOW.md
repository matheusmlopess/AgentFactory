# CI/CD Workflow
<!-- version: 1.0.0 -->

This document explains what CI/CD is, why AgentFactory uses it, and exactly how each workflow file operates.

---

## What is CI/CD?

**CI/CD** stands for **Continuous Integration / Continuous Delivery** (or Deployment). It is the practice of automating the steps that take code from a developer's machine to a verified, tested, and potentially shipped state — without manual intervention.

### Continuous Integration (CI)

Every time code is pushed or a pull request is opened, an automated pipeline runs a defined set of checks (linting, testing, coverage). The purpose is to catch problems **before** they reach the main branch, not after.

Without CI:
- A developer merges a PR that breaks tests nobody ran locally
- A typo in a CLI argument goes unnoticed for days
- Coverage quietly drops below an acceptable threshold

With CI:
- Every PR is blocked from merging unless all checks pass
- The team always has a green baseline on the default branch

### Continuous Delivery (CD)

CD extends CI by automating the steps that ship software to end users — in this project's case, publishing the `agentfactory-gen` package to PyPI and creating a GitHub Release. A tagged release triggers the pipeline; no manual build or upload steps are needed.

---

## Project Workflow Overview

```
Developer pushes code
        │
        ├─── to a branch + opens PR ──► CI pipeline runs
        │                                    │
        │                               lint → test → coverage
        │                                    │
        │                          ✓ pass → PR can be merged
        │                          ✗ fail → PR is blocked
        │
        └─── git tag v*.*.* ──────────► CD pipeline runs
                                             │
                                        build → GitHub Release
                                             │
                                        publish to PyPI
```

Branch protection on `dev` enforces that the **"Tests + Coverage"** CI status check must pass before any PR can be merged. Direct commits to `dev` are blocked.

---

## CI Pipeline — `.github/workflows/ci.yml`

**Trigger:** Every push to `dev` or `main`, and every pull request targeting those branches.

### Job 1: `lint`

```
ruff check src/
```

[Ruff](https://docs.astral.sh/ruff/) is an extremely fast Python linter. It checks for:
- Unused imports (`F401`)
- Unused variables (`F841`)
- Bare f-strings without placeholders (`F541`)
- Style issues that affect readability

This job runs **first and alone**. If it fails, the test matrix does not start — saving CI minutes.

### Job 2: `test` (matrix)

Runs **after** lint passes, in parallel across two Python versions:

| Matrix axis | Values |
|---|---|
| Python version | `3.11`, `3.12` |
| OS | `ubuntu-latest` |

Each matrix run:

1. **Checks out** the repository
2. **Installs** the package in editable mode with dev extras: `pip install -e ".[dev]"`  
   This installs `agentfactory-gen`, `pytest`, `pytest-cov`, and `ruff` as defined in `pyproject.toml`
3. **Runs the test suite with coverage:**
   ```
   pytest --cov=agent_gen --cov-report=term-missing --cov-fail-under=80
   ```
   - `--cov=agent_gen` — measures coverage over the `src/agent_gen/` package
   - `--cov-report=term-missing` — prints uncovered lines in CI logs
   - `--cov-fail-under=80` — the job **fails** if total coverage drops below 80%

Coverage thresholds are also configured in `pyproject.toml` under `[tool.coverage.report]` for local runs.

### Status check name

The job is named **"Tests + Coverage (Python X.Y)"**. The branch protection rule on `dev` requires the `Tests + Coverage` context to pass — meaning both matrix variants must pass before a PR can merge.

---

## CD Pipeline — `.github/workflows/release.yml`

**Trigger:** Any tag matching `v*` pushed to the repository (e.g. `v2.5.0`).

The release pipeline has three jobs that run after a shared **build** step.

### Job 1: `build`

```
python -m build
```

The [build](https://pypa-build.readthedocs.io/) tool reads `pyproject.toml` and produces two distribution artifacts in `dist/`:

| Artifact | Format | Purpose |
|---|---|---|
| `agent_gen-X.Y.Z-py3-none-any.whl` | Wheel | Fast installation via `pip install` |
| `agent_gen-X.Y.Z.tar.gz` | Source dist (sdist) | Archival and source inspection |

These artifacts are uploaded to the GitHub Actions artifact store so the downstream jobs can download them.

### Job 2: `github-release`

Creates a GitHub Release on the repository for the pushed tag. Steps:

1. **Extracts release notes** from `CHANGELOG.md` — finds the section matching the tag (e.g. `## [v2.5.0]`) and uses it as the release body
2. **Creates the Release** via [softprops/action-gh-release](https://github.com/softprops/action-gh-release) with the extracted notes and attaches the wheel + sdist as downloadable assets

This makes the release visible on GitHub's Releases page with a proper changelog entry and downloadable binaries.

### Job 3: `pypi-publish`

Publishes both artifacts to [PyPI](https://pypi.org/project/agentfactory-gen/) using [OIDC Trusted Publishing](https://docs.pypi.org/trusted-publishers/).

**How trusted publishing works (no secrets needed):**

Traditional PyPI publishing requires storing an API token in GitHub Secrets, which must be rotated and can be leaked. OIDC trusted publishing uses a short-lived identity token issued by GitHub Actions itself. PyPI verifies the token cryptographically — confirming it came from the right repo, branch, and workflow file — and grants publish access without any stored secret.

Configuration required once on PyPI (see setup section below).

The job runs in a GitHub Environment named **`pypi`**, which can be configured with required reviewers for an extra approval gate before publishing.

---

## How to Cut a Release

```bash
# 1. Make sure dev is clean and tests pass
git checkout dev
git pull

# 2. Update CHANGELOG.md — add a section for the new version
#    ## [v2.5.0] - 2026-04-13
#    ### Added
#    - ...

# 3. Update version in pyproject.toml
#    version = "0.3.0"

# 4. Commit
git add CHANGELOG.md pyproject.toml
git commit -m "chore: prepare release v2.5.0"

# 5. Tag and push — this triggers the CD pipeline
git tag -a v2.5.0 -m "v2.5.0: <one-line summary>"
git push origin dev
git push origin v2.5.0
```

The CD pipeline takes over: builds the package, creates the GitHub Release, and publishes to PyPI. No manual steps needed.

---

## One-Time PyPI Setup (Trusted Publishing)

Before the first release, configure OIDC trusted publishing on PyPI:

1. Log in to [pypi.org](https://pypi.org)
2. Go to your account → **Publishing** → **Add a new publisher**
3. Fill in:

   | Field | Value |
   |---|---|
   | PyPI project name | `agentfactory-gen` |
   | Owner | `matheusmlopess` |
   | Repository | `AgentFactory` |
   | Workflow filename | `release.yml` |
   | Environment name | `pypi` |

4. In the GitHub repository: **Settings → Environments → New environment** → name it `pypi`  
   Optionally add required reviewers for a manual approval gate before PyPI publish.

---

## Local Development

To run the same checks locally before pushing:

```bash
# Install dev dependencies (includes ruff, pytest, pytest-cov)
pip install -e ".[dev]"

# Lint
ruff check src/

# Fix auto-fixable lint issues
ruff check src/ --fix

# Tests with coverage
pytest --cov=agent_gen --cov-report=term-missing --cov-fail-under=80

# Run a single test
pytest src/tests/test_cli.py::TestCliCommands::test_e2e_lifecycle

# Build distribution locally (optional)
pip install build
python -m build
```

---

## File Reference

| File | Purpose |
|---|---|
| `.github/workflows/ci.yml` | CI: lint + test matrix on push/PR |
| `.github/workflows/release.yml` | CD: build + GitHub Release + PyPI publish on tag |
| `pyproject.toml` | Dev dependencies, coverage config, package metadata |
| `src/tests/` | Test suite (46 tests across 6 files) |
