# AgentFactory
<!-- version: 2.9.0 -->

A Python CLI (`agentfactory-gen`) for building, packaging, and deploying AI agents
as portable, framework-agnostic units. The web platform lives at
[agentfactory-webapp](https://github.com/matheusmlopess/agentfactory-webapp) (private).

AgentFactory provides a **Unified AI Harness** — a single `.ai/` directory that lets
Claude, Codex, and Gemini work on the same project simultaneously, each reading a
compiled brief tailored to their format while sharing the same skills, rules, and
agent manifest.

---

## Project Layout

```
project/
├── CLAUDE.md  → .ai/adapters/claude/brief.md   ← Claude Code reads this
├── AGENTS.md  → .ai/adapters/codex/brief.md    ← Codex reads this
├── GEMINI.md  → .ai/adapters/gemini/brief.md   ← Gemini reads this
├── .claude    → .ai/adapters/claude/
├── .codex     → .ai/adapters/codex/
├── .gemini    → .ai/adapters/gemini/
└── .ai/
    ├── AgentFactory.md          ← master compiled brief (preamble + registries + rules + commands)
    ├── agent-manifest.json      ← global agent registry
    ├── config/
    │   └── completeness.json    ← per-adapter skill completeness thresholds
    ├── adapters/
    │   ├── claude/   brief.md, settings.json, skills →, commands →
    │   ├── codex/    brief.md, config.toml, skills →, prompts →
    │   └── gemini/   brief.md, config.json, tools →
    ├── rules/        ← project constraints (compiled into every brief)
    ├── skills/       ← reusable SKILL.md specs + manifests
    ├── commands/     ← slash commands (Claude) + prompts (Codex)
    ├── agents/       ← deployed agent directories
    ├── memory/       ← milestones traceability matrix
    ├── reports/      ← skill completeness JSON reports
    └── scripts/      ← harness-doctor.sh, skill-completeness-check.py, …
```

Every adapter brief starts with a **Harness Identity Block** — a standard section
that maps all adapter briefs and shared context paths, including a direct reference
to `.ai/AgentFactory.md`. Any agent picking up the project for the first time (or
after a CLI swap) can navigate the full harness immediately.

Every adapter brief also carries a **Project Context** section: the human-written
preamble from `.ai/AgentFactory.md`, budget-fitted per adapter (claude/gemini: 4 000
chars, codex: 2 000 chars). This closes the context gap that existed when switching
CLIs mid-project.

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

# 3. Audit integrity
agentfactory-gen audit my-agent

# 4. Package into a Portable Unit
agentfactory-gen wrap my-agent

# 5. Import a remote agent in one step
agentfactory-gen import --from-git https://github.com/user/some-agent-repo

# 6. Activate a second CLI adapter (e.g. switching to Codex mid-project)
agentfactory-gen adapter add codex

# 7. Recompile all active adapter briefs
agentfactory-gen brief
```

---

## CLI Reference

### Setup & Adapters

```bash
agentfactory-gen init                              # scaffold .ai/ harness + root symlinks
agentfactory-gen init --project-root <path>        # target a different directory

agentfactory-gen adapter add <name>                # activate a CLI adapter (claude/codex/gemini)
agentfactory-gen adapter add <name> \
  --check-completeness                             # also run skill completeness gate
agentfactory-gen adapter add <name> --strict       # exit non-zero if any skill fails threshold

agentfactory-gen brief                             # recompile all active adapter briefs
```

### Agent Lifecycle

```bash
agentfactory-gen deploy <name>               # scaffold a new agent
agentfactory-gen describe <name> --desc "…"  # set agent description
agentfactory-gen describe <name> --plan <p>  # set orchestration plan path
agentfactory-gen audit <name>                # check for missing files, broken deps, version drift
agentfactory-gen wrap <name>                 # compress agent into a Portable Unit ZIP
agentfactory-gen wrap <name> --out <dir>     # write ZIP to a specific directory
agentfactory-gen import <zip>                # unpack ZIP and register agent
agentfactory-gen import --from-git <url>     # clone repo, auto-retrofit, and import
agentfactory-gen import --from-registry <slug>  # download and install from public registry
agentfactory-gen export <name>               # patch a locally-edited agent back to its source repo (branch + PR)
agentfactory-gen export <name> --git <url>   # … to an explicit source; --no-push writes a .patch
agentfactory-gen publish <name>              # upload wrapped agent to public registry
agentfactory-gen publish <name> --version <v> --tag <t>  # override version and add tags
agentfactory-gen uninstall <name>            # remove agent cleanly
```

### Skills

```bash
agentfactory-gen import-skill <path>                  # import skill into .ai/skills/
agentfactory-gen import-skill <path> --to <agent>     # import into a specific agent
agentfactory-gen retrofit <path>                      # convert Claude/Gemini/Codex layout

# Skill completeness oracle
python3 .ai/scripts/skill-completeness-check.py --skill <name> --adapter <adapter>
python3 .ai/scripts/skill-completeness-check.py --agent <name> --adapter <adapter>
python3 .ai/scripts/skill-completeness-check.py --skill <name> --mode new   # new skill self-check [pro]
python3 .ai/scripts/skill-completeness-check.py --skill <name> --oracle-model claude-sonnet-4-6
```

### Global flag

```bash
agentfactory-gen -q <command>               # suppress informational output (quiet mode)
```

---

## Key Features

### Compiled Per-Adapter Briefs (FormatSwitch)

Each adapter receives a brief compiled to its format:

| Adapter | Root file | Skill format |
|---------|-----------|-------------|
| Claude | `CLAUDE.md` | Markdown table with path references |
| Codex | `AGENTS.md` + `CODEX.md` | Block declarations with `use when:` |
| Gemini | `GEMINI.md` | Tool-style blocks with `input:` |

Every brief includes a universal **Harness Identity Block** at the top — adapter
name, harness root, shared context paths, and a cross-adapter table so any agent
can navigate to the other briefs after a CLI swap.

Recompile all active briefs: `agentfactory-gen brief`

### Project Context Injection & Master Brief

Every adapter brief gets a `## Project Context` section automatically — the
human-written preamble from `.ai/AgentFactory.md`, trimmed to fit the adapter's
character budget:

| Adapter | Context limit | Behaviour on overflow |
|---------|--------------|----------------------|
| Claude | 4 000 chars | Full preamble |
| Gemini | 4 000 chars | Full preamble |
| Codex | 2 000 chars | Truncated at paragraph boundary + `<!-- ⚠ context truncated -->` comment |

When truncation occurs and `AGENTFACTORY_LICENSE_KEY` is set, the completeness oracle
runs automatically during `agentfactory-gen brief` and prints the information-retention
score to stderr — no manual invocation needed:

```
⚠ preamble completeness: 74%
```

The check is **advisory only**: it never blocks compilation or changes brief content.
It tells you how much of the original preamble's meaning survived the truncation so
you can decide whether to shorten the preamble or raise the adapter's `context_char_limit`.

`AgentFactory.md` is also compiled as a **full master brief**: `agentfactory-gen brief`
upserts `<!-- @commands-start/end -->` and `<!-- @rules-start/end -->` sections so it
has the same richness as any adapter brief. Reading it directly gives a complete
picture of the project.

```bash
# After editing your project overview in .ai/AgentFactory.md:
agentfactory-gen brief
# → All adapter briefs updated with new preamble
# → AgentFactory.md updated with latest rules + commands
# → If truncation occurred and AGENTFACTORY_LICENSE_KEY is set:
#   ⚠ preamble completeness: X%  (printed to stderr, advisory)
```

Full reference: [`docs/FEATURE-AGENTFACTORY-MD-BRIEF.md`](docs/FEATURE-AGENTFACTORY-MD-BRIEF.md)

### Codex Study Docs

For a deeper view of Codex-specific project discovery, init behavior, and issue-ready
gap analysis, see:

- [`docs/STUDY-CODEX-PROJECT-MAPPING.md`](docs/STUDY-CODEX-PROJECT-MAPPING.md)
- [`docs/STUDY-CODEX-INIT-SCENARIOS.md`](docs/STUDY-CODEX-INIT-SCENARIOS.md)
- [`docs/STUDY-CODEX-GAP-MATRIX.md`](docs/STUDY-CODEX-GAP-MATRIX.md)

### Gemini Study Docs

For the Gemini adapter alignment study and the bridge plan for moving from the
legacy `tools` / `config.json` layout to Gemini-native conventions, see:

- [`docs/STUDY-GEMINI-ALIGNMENT.md`](docs/STUDY-GEMINI-ALIGNMENT.md)

### Skill Completeness Oracle

A two-phase Claude Haiku oracle that verifies a trimmed `SKILL.md` preserves all
functional capability of the original. Supports global skills, agents, and new
uncommitted skills via Phase 0 auto-trim.

```bash
# Existing committed skill (free)
python3 .ai/scripts/skill-completeness-check.py \
  --skill git-versioning --adapter claude

# New/uncommitted skill self-check (pro)
python3 .ai/scripts/skill-completeness-check.py \
  --skill my-new-skill --mode new --adapter claude

# All skills in an agent (pro)
python3 .ai/scripts/skill-completeness-check.py \
  --agent test-agent --adapter claude

# Higher accuracy
python3 .ai/scripts/skill-completeness-check.py \
  --skill git-versioning --oracle-model claude-sonnet-4-6
```

Phase 1 extracts **functional atoms** (commands, decision paths, error cases,
constraints) from the original using ephemeral prompt cache. Phase 2 verifies each
atom is present in the trimmed version. Score ≥ threshold → pass.

**Modes:** `--mode auto` (default, detects new vs committed) · `--mode new` (force
Phase 0 trim) `[pro]` · `--mode diff` (force git baseline, fails if no baseline)

**Models:** Haiku ~1× cost (default) · Sonnet ~6× · Opus ~20×

Per-adapter thresholds in `.ai/config/completeness.json`:

```json
{ "completeness": { "thresholds": { "claude": 90, "codex": 95, "gemini": 90 } } }
```

Integrated into: pre-commit hook · dedicated CI job · `adapter add --check-completeness`

Full how-to: [`docs/HOWTO-COMPLETENESS-CHECK.md`](docs/HOWTO-COMPLETENESS-CHECK.md)

### Harness Doctor

Live health check for the `.ai/` harness:

```bash
bash .ai/scripts/harness-doctor.sh            # structural checks
bash .ai/scripts/harness-doctor.sh --completeness  # + semantic skill checks (requires API key)
bash .ai/scripts/harness-doctor.sh --ci       # machine-readable for CI
```

Exit codes: `0` clean · `1` warnings · `2` critical violations

### `--from-git` Import

```bash
agentfactory-gen import --from-git https://github.com/user/repo
```

Clones, reads `README.md` and `CLAUDE.md` for descriptions, auto-detects and applies
the correct retrofit profile, creates `skill-manifest.json` stubs, and registers the
result in the harness.

---

## CI/CD

| Trigger | Workflow | What runs |
|---------|----------|-----------|
| Push / PR (any branch) | `ci.yml` | ruff lint → pytest (3.11 + 3.12) → coverage ≥ 80% → harness-doctor |
| Push / PR (SKILL.md changed) | `skill-completeness.yml` | two-phase completeness oracle per skill |
| Push to `dev` / `main` | `issue-tracker.yml` | regenerate `docs/ISSUE-PRIORITY.md` |
| `git tag v*` | `release.yml` | build wheel + sdist → GitHub Release → PyPI |

Branch protection on `dev` requires **Tests + Coverage** to pass before merge.

---

## Documentation

| Doc | What it covers |
|-----|---------------|
| [`docs/FEATURE-WORKFLOW.md`](docs/FEATURE-WORKFLOW.md) | 8-step feature lifecycle (issue → branch → implement → CI → PR → merge → milestones → report) |
| [`docs/SKILL-COMPLETENESS-SPEC.md`](docs/SKILL-COMPLETENESS-SPEC.md) | Two-phase oracle, CLI reference, all integration points |
| [`docs/HOWTO.md`](docs/HOWTO.md) | Workflow diagrams: deploy, retrofit, wrap, import, uninstall |
| [`docs/FEATURE-AGENTFACTORY-MD-BRIEF.md`](docs/FEATURE-AGENTFACTORY-MD-BRIEF.md) | Master brief & project context injection: workflow diagrams, gap analysis, CLI switch walkthrough |
| [`docs/FEATURE-HARNESS-IDENTITY.md`](docs/FEATURE-HARNESS-IDENTITY.md) | Cross-adapter navigation block: how it works, swap walkthrough |
| [`docs/FEATURE-REGISTRY-CLI.md`](docs/FEATURE-REGISTRY-CLI.md) | Registry CLI commands: `publish` upload flow, `import --from-registry` download flow, all scenarios |
| [`docs/FEATURE-DOC-TEMPLATE.md`](docs/FEATURE-DOC-TEMPLATE.md) | Blank template — every new feature ships one of these |
| [`docs/ISSUE-PRIORITY.md`](docs/ISSUE-PRIORITY.md) | Live issue priority + wave map (auto-regenerated on every merge) |
| [`docs/SPEC.md`](docs/SPEC.md) | Technical specification: manifest schema, intelligence layer |
| [`docs/HOWTO-COMPLETENESS-CHECK.md`](docs/HOWTO-COMPLETENESS-CHECK.md) | All completeness check modes: skill, agent, new-skill, model selection |

---

## Contributing

Install dev dependencies and git hooks:

```bash
pip install -e ".[dev]"
cp .ai/scripts/pre-commit-completeness.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

Every contribution follows the 8-step lifecycle in `docs/FEATURE-WORKFLOW.md`.
Features that introduce new public behaviour must ship with a `docs/FEATURE-<name>.md`.

---

## Registered Agents
<!-- @agent-registry:start -->
- **security-review**: Produces dated REVIEW-SECURITY-ARCHITECTURE-YYYY-MM-DD.md reports: component matrix, Mermaid diagrams, SEV-classified security findings, design gaps, and a prioritised recommendations table. (See: `.ai/agents/security-review/docs/CLAUDE.md`)
- **test-agent**: Manual Description (See: `.ai/agents/test-agent/docs/CLAUDE.md`)
- **test-claude-agent**: AgentFactory-powered agent demonstrating a minimal Claude-native agent layout. (See: `.ai/agents/test-claude-agent/docs/CLAUDE.md`)
- **test-intel-agent**: AgentFactory-powered agent demonstrating intelligence-layer features: dependency detection and skill manifest parsing. (See: `.ai/agents/test-intel-agent/docs/CLAUDE.md`)
<!-- @agent-registry:end -->

## Available Skills
<!-- @skills-registry:start -->
- **diff-visualizer**: Generates HTML diff reports visualizing what changed between two versions of the repo. (See: `.ai/skills/diff-visualizer/SKILL.md`)
- **git-versioning**: Manages project-wide versioning and repo-state.md updates. (See: `.ai/skills/git-versioning/SKILL.md`)
- **issue-tracker**: Regenerates the issue priority report and dependency matrix from live GitHub data. (See: `.ai/skills/issue-tracker/SKILL.md`)
<!-- @skills-registry:end -->
