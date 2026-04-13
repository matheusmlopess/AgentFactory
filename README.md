# AgentFactory
<!-- version: 2.5.0 -->

A lightweight Python CLI (`agent-gen`) for building, packaging, and deploying AI agents as portable, framework-agnostic units.

AgentFactory provides a **Unified AI Harness** — a single `.ai/` directory that lets Claude, Codex, and Gemini work on the same project simultaneously, sharing context without conflicts.

---

## Workflows

### 1. Overall Architecture

```mermaid
graph TD
    subgraph Project Root
        CM[CLAUDE.md]
        AM[AGENTS.md]
        GM[GEMINI.md]
        CO[CODEX.md]
        CL[.claude]
        GE[.gemini]
        CD[.codex]
    end

    subgraph ".ai/ — Unified Harness"
        AF[AgentFactory.md\nsingle source of truth]
        MF[agent-manifest.json\nglobal registry]

        subgraph adapters/
            ACA[claude/\nsettings.json]
            AGE[gemini/\nconfig.json]
            ACO[codex/\nconfig.toml]
        end

        subgraph shared/
            RU[rules/]
            SK[skills/]
            CMD[commands/]
            AG[agents/]
            MEM[memory/\nmilestones.md]
        end
    end

    CM -->|symlink| AF
    AM -->|symlink| AF
    GM -->|symlink| AF
    CO -->|symlink| AF
    CL -->|symlink| ACA
    GE -->|symlink| AGE
    CD -->|symlink| ACO

    ACA -->|commands →| CMD
    ACA -->|skills →| SK
    AGE -->|tools →| SK
    ACO -->|prompts →| CMD
```

---

### 2. Agent Lifecycle

```mermaid
flowchart LR
    A([Start]) --> B[agent-gen deploy name]
    B --> C[Scaffold 5-dir structure\nskills commands docs\nscripts orchestration]
    C --> D[Init agent-manifest.json\nvia Librarian.init]

    D --> E[agent-gen describe\n--desc --plan]
    E --> F[Update manifest\nmetadata]

    F --> G[Develop\nadd skills commands docs]

    G --> H[agent-gen audit name]
    H --> I{Clean?}
    I -->|broken deps\nor missing files| G
    I -->|pass| J[agent-gen wrap name]

    J --> K[Librarian.sync\ncrawl disk → manifest]
    K --> L[Librarian.audit\nvalidate all paths]
    L --> M{Audit pass?}
    M -->|fail| G
    M -->|pass| N[Compress → name-vX.Y.Z.zip\nPortable Unit]

    N --> O[Share ZIP]
    O --> P[agent-gen import zip]
    P --> Q[Unpack into .ai/agents/name]
    Q --> R[Audit imported bundle]
    R --> S[Handshake\nregister in global manifest]
    S --> T([Agent ready])

    T --> U[agent-gen uninstall name]
    U --> V[Remove dir\nDeregister from manifest]
```

---

### 3. Remote Import Pipeline (`--from-git`)

```mermaid
flowchart TD
    A[agent-gen import\n--from-git URL] --> B{Valid URL scheme?\nhttps git@ ssh}
    B -->|no| ERR1([Error: invalid URL])
    B -->|yes| C[git clone --quiet URL]
    C --> D{Clone success?}
    D -->|no| ERR2([Error: clone failed])
    D -->|yes| E[Extract context\nfrom README.md + CLAUDE.md]

    E --> F[propose_retrofit\ndetect profile]
    F --> G{Profile detected?}
    G -->|claude / gemini / codex| H[Warn if multiple\nprofiles matched]
    G -->|auto| I[Apply auto-rules]
    H --> J[Librarian.migrate\nremap dirs to 5-dir standard]
    I --> J

    J --> K[Auto-stub\nskill-manifest.json files]
    K --> L[Init agent-manifest.json\ninject description from context]
    L --> M[Librarian.wrap\ncompress to ZIP]
    M --> N[Unpack + Audit]
    N --> O{Audit pass?}
    O -->|fail| ERR3([Error: abort import])
    O -->|pass| P[Register in\nglobal manifest]
    P --> Q[Cleanup temp dir]
    Q --> R([Import complete\nAgent ready])
```

---

### 4. Librarian Intelligence Layer

```mermaid
flowchart TD
    subgraph Librarian.sync
        A[Crawl agent root\nTRACKED_DIRS] --> B[Update resources\nin manifest]
        B --> C[_detect_dependencies\nper resource file]
        C --> D{File type?}
        D -->|.py| E[AST import parser\nextract module names]
        D -->|.md / other| F[Regex scan\nfor @depends-on: markers]
        E --> G[Write dependencies\nmap to manifest]
        F --> G
        G --> H[_detect_orchestration\nfirst file in orchestration/]
        H --> I[_update_skills_metadata\nparse skill-manifest.json files]
        I --> J[Save manifest]
    end

    subgraph Librarian.audit
        J --> K[validate\ncheck all resource paths exist]
        K --> L[Check broken dependencies\ncross-file refs missing on disk]
        L --> M[Check untracked files\non disk but not in manifest]
        M --> N[Check missing\nskill-manifest.json]
        N --> O[Check skill version drift\nskill-manifest vs SKILL.md frontmatter]
        O --> P[_check_repo_state\nlatest tag + remote URL match]
        P --> Q([Return audit report])
    end
```

---

### 5. Multi-CLI Harness — Adapter Wiring

```mermaid
graph LR
    subgraph ".ai/ shared"
        SK[skills/]
        CMD[commands/]
    end

    subgraph ".ai/adapters/claude/"
        CS[skills →]
        CC[commands →]
        CSET[settings.json]
    end

    subgraph ".ai/adapters/gemini/"
        GT[tools →]
        GCFG[config.json]
    end

    subgraph ".ai/adapters/codex/"
        CP[prompts →]
        CCFG[config.toml]
    end

    CS -->|symlink| SK
    CC -->|symlink| CMD
    GT -->|symlink| SK
    CP -->|symlink| CMD

    CLAUDE([Claude Code]) --> CS
    CLAUDE --> CC
    GEMINI([Gemini CLI]) --> GT
    CODEX([Codex CLI]) --> CP
```

---

### 6. CI Pipeline (every push / PR)

```mermaid
flowchart TD
    A([Push or PR\nto dev / main]) --> B

    subgraph ci.yml
        B[Job: lint\nruff check src/] --> C{Lint pass?}
        C -->|fail| STOP1([Block — fix lint errors])
        C -->|pass| D

        D[Job: test matrix\nPython 3.11 + 3.12\nin parallel]
        D --> E[pip install -e '.[dev]']
        E --> F[pytest\n--cov=agent_gen\n--cov-fail-under=80]
        F --> G{Tests + Coverage\n≥ 80%?}
        G -->|fail| STOP2([Block — fix tests\nor add coverage])
        G -->|pass| H([Status check green\nTests + Coverage ✓])
    end

    H --> I{Is this a PR\nto dev?}
    I -->|yes| J[Branch protection gate\nrequires green status]
    J --> K([PR can be merged])
```

---

### 7. CD Pipeline (on version tag)

```mermaid
flowchart TD
    A([git tag vX.Y.Z\ngit push origin vX.Y.Z]) --> B

    subgraph release.yml
        B[Job: build] --> C[pip install build]
        C --> D[python -m build]
        D --> E[Produce dist/\nwheel + sdist]
        E --> F[Upload artifacts\nto Actions store]

        F --> G[Job: github-release\nruns after build]
        G --> H[Extract release notes\nfrom CHANGELOG.md]
        H --> I[Create GitHub Release\nattach wheel + sdist]

        F --> J[Job: pypi-publish\nruns after build]
        J --> K[OIDC trusted publish\nno token secret needed]
        K --> L([Published to PyPI\npypi.org/project/agentfactory-gen])
    end

    I --> M([Release visible\non GitHub Releases page])
```

---

### 8. Traceability / Milestone Update Workflow

```mermaid
flowchart TD
    A([Work starts\non an issue]) --> B[Create feature branch\nfix/feat/docs/upgrade]
    B --> C[Implement changes]
    C --> D[Push branch\nOpen PR]
    D --> E[CI runs\nlint + tests + coverage]
    E --> F{CI green?}
    F -->|no| C
    F -->|yes| G[PR review + merge]

    G --> H[Update .ai/memory/milestones.md\nStep 8.5 of git-versioning skill]
    H --> I[Move issue row\nPending → Completed]
    I --> J[Fill Branch / PR / Commit]
    J --> K{Is this a\nrelease commit?}
    K -->|yes| L[Stamp Tag column\nfor all shipped items]
    K -->|no| M[Bump milestones.md\nversion marker PATCH]
    L --> M
    M --> N[git tag vX.Y.Z\ntriggers CD pipeline]
    N --> O([GitHub Release\n+ PyPI publish])
```

---

## Project Layout

```text
project/
├── CLAUDE.md  → .ai/AgentFactory.md   ← auto-loaded by Claude
├── AGENTS.md  → .ai/AgentFactory.md   ← auto-loaded by Codex  (same file)
├── GEMINI.md  → .ai/AgentFactory.md   ← auto-loaded by Gemini (same file)
├── CODEX.md   → .ai/AgentFactory.md   ← alias (same file)
├── .claude    → .ai/adapters/claude
├── .gemini    → .ai/adapters/gemini
├── .codex     → .ai/adapters/codex
└── .ai/
    ├── AgentFactory.md      ← single source of truth for all CLI instructions
    ├── agent-manifest.json  ← global agent registry
    ├── adapters/            ← per-CLI config + capability symlinks
    │   ├── claude/          settings.json, commands →, skills →
    │   ├── gemini/          config.json, tools → skills
    │   └── codex/           config.toml, prompts → commands
    ├── rules/               ← enforceable project constraints
    ├── commands/            ← Claude slash commands + Codex prompts (unified)
    ├── skills/              ← reusable deep-context workflows + Gemini tools
    ├── agents/              ← deployed agent directories
    ├── memory/              ← project state + milestones traceability matrix
    └── scripts/             ← harness utilities (harness-doctor.sh)
```

Each agent under `.ai/agents/<name>/` follows the **5-Directory Standard**:
`skills/` · `commands/` · `docs/` · `scripts/` · `orchestration/`

---

## Installation

```bash
pip install agentfactory-gen
```

Or install from source (editable):

```bash
git clone https://github.com/matheusmlopess/AgentFactory.git
cd AgentFactory
pip install -e ".[dev]"
```

Requires Python 3.11+.

---

## Quick Start

```bash
# 1. Initialise the harness in your project
agent-gen init

# 2. Deploy your first agent
agent-gen deploy my-agent

# 3. Set a description
agent-gen describe my-agent --desc "My first AgentFactory agent"

# 4. Audit integrity
agent-gen audit my-agent

# 5. Package into a Portable Unit
agent-gen wrap my-agent

# 6. Import a remote agent in one step
agent-gen import --from-git https://github.com/user/some-agent-repo
```

---

## CLI Reference

### Setup
```bash
agent-gen init                        # scaffold .ai/ harness + root symlinks
agent-gen init --project-root <path>  # target a different directory
```

### Agent Lifecycle
```bash
agent-gen deploy <name>               # scaffold a new agent
agent-gen describe <name> --desc "…"  # set agent description
agent-gen describe <name> --plan <p>  # set orchestration plan path
agent-gen audit <name>                # check for missing files, broken deps, version drift
agent-gen wrap <name>                 # compress agent into a shareable ZIP (Portable Unit)
agent-gen wrap <name> --out <dir>     # write ZIP to a specific directory
agent-gen import <zip>                # unpack ZIP and register agent
agent-gen import --from-git <url>     # clone repo, auto-retrofit, and import in one step
agent-gen uninstall <name>            # remove agent cleanly
```

### Skills & Intelligence
```bash
agent-gen import-skill <path>                  # import skill into root .ai/skills/
agent-gen import-skill <path> --to <agent>     # import into a specific agent
agent-gen retrofit <path>                      # convert Claude/Gemini/Codex layout to AgentFactory standard
```

### Global flag
```bash
agent-gen -q <command>               # suppress all informational output (quiet mode)
```

---

## Key Features

**`--from-git`** — Import any GitHub repo as an agent in one command:
```bash
agent-gen import --from-git https://github.com/user/repo
```
Reads `README.md` and `CLAUDE.md` to extract descriptions, auto-detects and applies the correct retrofit profile, creates `skill-manifest.json` stubs for sub-agents, and registers the result in `.ai/AgentFactory.md`.

**Librarian** (`src/agent_gen/librarian.py`) — core engine behind every lifecycle operation:
- Manifest integrity validation
- AST-based dependency detection (Python imports + `<!-- @depends-on: -->` annotations)
- Skill manifest auto-registration
- Audit: version drift, repo-state staleness, remote URL mismatch, path traversal protection

**Harness Doctor** (`.ai/scripts/harness-doctor.sh`) — live health check:
```bash
bash .ai/scripts/harness-doctor.sh        # full report
bash .ai/scripts/harness-doctor.sh --ci   # machine-readable + snapshot JSON
```
Exit codes: `0` clean · `1` warnings · `2` critical violations.

---

## CI/CD

| Trigger | Workflow | What runs |
|---|---|---|
| Push / PR to `dev` or `main` | `ci.yml` | ruff lint → pytest (3.11 + 3.12) → coverage ≥ 80% |
| `git tag v*` | `release.yml` | build wheel/sdist → GitHub Release → PyPI publish |

Branch protection on `dev` requires the **Tests + Coverage** status check to pass before any PR can merge.

See [`docs/CICD-WORKFLOW.md`](docs/CICD-WORKFLOW.md) for a full explanation of both pipelines.

---

## Architecture & Contributing

See `.ai/AgentFactory.md` for architecture, domain context, and project constraints.
See `docs/SPEC.md` for the technical specification (manifest schema, intelligence layer, lifecycle commands).
Contributions should follow the rules in `.ai/rules/`.

---

## Registered Agents
<!-- @agent-registry:start -->
- **test-agent**: Manual Description (See: `.ai/agents/test-agent/docs/CLAUDE.md`)
- **test-claude-agent**: AgentFactory-powered agent demonstrating a minimal Claude-native agent layout. (See: `.ai/agents/test-claude-agent/docs/CLAUDE.md`)
- **test-intel-agent**: AgentFactory-powered agent demonstrating intelligence-layer features: dependency detection and sk... (See: `.ai/agents/test-intel-agent/docs/CLAUDE.md`)
<!-- @agent-registry:end -->
