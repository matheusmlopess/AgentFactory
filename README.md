# AgentFactory
<!-- version: 2.6.1 -->

A lightweight Python CLI (`agentfactory-gen`) for building, packaging, and deploying AI agents as portable, framework-agnostic units.

AgentFactory provides a **Unified AI Harness** — a single `.ai/` directory that lets Claude, Codex, and Gemini work on the same project simultaneously, sharing context without conflicts.

---

## Project Layout

```text
project/
├── CLAUDE.md  → .ai/AgentFactory.md   ← auto-loaded by Claude
├── AGENTS.md  → .ai/AgentFactory.md   ← auto-loaded by Codex
├── GEMINI.md  → .ai/AgentFactory.md   ← auto-loaded by Gemini
├── .claude    → .ai/adapters/claude
├── .gemini    → .ai/adapters/gemini
├── .codex     → .ai/adapters/codex
└── .ai/
    ├── AgentFactory.md       ← single source of truth for all CLI instructions
    ├── agent-manifest.json   ← global agent registry
    ├── adapters/             ← per-CLI config + capability symlinks
    │   ├── claude/           settings.json, commands →, skills →
    │   ├── gemini/           config.json, tools → skills
    │   └── codex/            config.toml, prompts → commands
    ├── rules/                ← enforceable project constraints
    ├── commands/             ← Claude slash commands + Codex prompts (unified)
    ├── skills/               ← reusable deep-context workflows + Gemini tools
    ├── agents/               ← deployed agent directories
    ├── memory/               ← project state + milestones traceability matrix
    └── scripts/              ← harness utilities (harness-doctor.sh)
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
agentfactory-gen init

# 2. Deploy your first agent
agentfactory-gen deploy my-agent

# 3. Set a description
agentfactory-gen describe my-agent --desc "My first AgentFactory agent"

# 4. Audit integrity
agentfactory-gen audit my-agent

# 5. Package into a Portable Unit
agentfactory-gen wrap my-agent

# 6. Import a remote agent in one step
agentfactory-gen import --from-git https://github.com/user/some-agent-repo
```

---

## CLI Reference

### Setup
```bash
agentfactory-gen init                        # scaffold .ai/ harness + root symlinks
agentfactory-gen init --project-root <path>  # target a different directory
```

### Agent Lifecycle
```bash
agentfactory-gen deploy <name>               # scaffold a new agent
agentfactory-gen describe <name> --desc "…"  # set agent description
agentfactory-gen describe <name> --plan <p>  # set orchestration plan path
agentfactory-gen audit <name>                # check for missing files, broken deps, version drift
agentfactory-gen wrap <name>                 # compress agent into a shareable ZIP (Portable Unit)
agentfactory-gen wrap <name> --out <dir>     # write ZIP to a specific directory
agentfactory-gen import <zip>                # unpack ZIP and register agent
agentfactory-gen import --from-git <url>     # clone repo, auto-retrofit, and import in one step
agentfactory-gen uninstall <name>            # remove agent cleanly
```

### Skills & Intelligence
```bash
agentfactory-gen import-skill <path>                  # import skill into root .ai/skills/
agentfactory-gen import-skill <path> --to <agent>     # import into a specific agent
agentfactory-gen retrofit <path>                      # convert Claude/Gemini/Codex layout to AgentFactory standard
```

### Global flag
```bash
agentfactory-gen -q <command>               # suppress all informational output (quiet mode)
```

---

## Key Features

**`--from-git`** — Import any GitHub repo as an agent in one command:
```bash
agentfactory-gen import --from-git https://github.com/user/repo
```
Reads `README.md` and `CLAUDE.md` to extract descriptions, auto-detects and applies the correct retrofit profile, creates `skill-manifest.json` stubs for sub-agents, and registers the result in `.ai/AgentFactory.md`.

**Librarian** (`src/agent_gen/librarian.py`) — core engine behind every lifecycle operation:
- Manifest integrity validation
- AST-based dependency detection (Python imports + `<!-- @depends-on: -->` annotations)
- Skill manifest auto-registration
- Audit: version drift, repo-state staleness, remote URL mismatch, path traversal protection
- ZIP Slip guard and prompt injection sanitization on all registry writes

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
| `git tag v*` | `deploy-webapp.yml` | install webapp deps → `npm run build` → publish `webapp/dist` to GitHub Pages |

Branch protection on `dev` requires the **Tests + Coverage** status check to pass before any PR can merge.

Live demo placeholder: `https://matheusmlopess.github.io/AgentFactory/`

---

## Architecture & Contributing

- [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) — architecture, lifecycle, and pipeline diagrams
- [`docs/CICD-WORKFLOW.md`](docs/CICD-WORKFLOW.md) — full CI/CD pipeline explainer
- [`docs/SPEC.md`](docs/SPEC.md) — technical specification (manifest schema, intelligence layer, lifecycle commands)
- `.ai/AgentFactory.md` — domain context and project constraints (auto-loaded by Claude)
- Contributions should follow the rules in `.ai/rules/`

---

## Registered Agents
<!-- @agent-registry:start -->
- **test-agent**: Manual Description (See: `.ai/agents/test-agent/docs/CLAUDE.md`)
- **test-claude-agent**: AgentFactory-powered agent demonstrating a minimal Claude-native agent layout. (See: `.ai/agents/test-claude-agent/docs/CLAUDE.md`)
- **test-intel-agent**: AgentFactory-powered agent demonstrating intelligence-layer features: dependency detection and skill manifest parsing. (See: `.ai/agents/test-intel-agent/docs/CLAUDE.md`)
<!-- @agent-registry:end -->
