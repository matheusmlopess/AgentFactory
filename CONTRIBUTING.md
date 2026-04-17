# Contributing to AgentFactory
<!-- version: 1.0.0 -->

## Dev Setup

```bash
git clone https://github.com/matheusmlopess/AgentFactory.git
cd AgentFactory
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Install Git Hooks

Run this once after cloning — hooks are not tracked by git:

```bash
cp .ai/scripts/pre-commit-completeness.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

**What the hook does:**

```
  git commit (with .ai/skills/**/SKILL.md staged)
      │
      ▼
  ⚠  SKILL.md staged — consider running:
     python3 .ai/scripts/skill-completeness-check.py --skill <name>
     Continue? [y/N]
```

Warns when a `SKILL.md` is staged. Interactive prompt in terminal;
silent pass in CI (no TTY). Bypass any time with:

```bash
SKIP_COMPLETENESS_WARN=1 git commit ...
```

## Feature Workflow

Every contribution follows the 8-step lifecycle in `docs/FEATURE-WORKFLOW.md`:

```
  ① Issue  →  ② Branch  →  ③ Implement  →  ④ CI gates
  →  ⑤ PR  →  ⑥ Merge  →  ⑦ Milestones  →  ⑧ Priority report
```

## Running Checks Locally

```bash
# Harness health
bash .ai/scripts/harness-doctor.sh

# Skill completeness (requires ANTHROPIC_API_KEY)
python3 .ai/scripts/skill-completeness-check.py --skill <name>

# Issue priority report
python3 .ai/scripts/generate-priority-report.py --dry-run

# Tests
pytest src/tests/ -q
```
