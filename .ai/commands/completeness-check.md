# Completeness Check
<!-- version: 1.1.0 -->

Run the skill completeness oracle to verify that a SKILL.md preserves all
functional behaviour after trimming, or to self-audit a new skill or agent
before committing.

> **Pro plan required** for `--mode new`, `--mode auto` on uncommitted skills,
> and all `--agent` checks. Diff mode on committed skills is free.
> Set plan: `echo '{"plan":"pro"}' > .ai/config/user.json`

> **Claude access:** uses your Claude subscription through Claude Code by default (`claude auth login`).
> `ANTHROPIC_API_KEY` is an optional fallback; force one with `--claude-backend subscription|api`.
> Check with `--check-access`.

## Commands

- **Check global skill (free):**
  `python3 .ai/scripts/skill-completeness-check.py --skill <name> --adapter <adapter>`

- **Check all skills in an agent (pro):**
  `python3 .ai/scripts/skill-completeness-check.py --agent <name> --adapter <adapter>`

- **New skill self-audit (pro):**
  `python3 .ai/scripts/skill-completeness-check.py --skill <name> --mode new --adapter <adapter>`

- **Force diff mode (no fallback):**
  `python3 .ai/scripts/skill-completeness-check.py --skill <name> --mode diff`

- **Higher accuracy:**
  Add `--oracle-model sonnet`

## Modes

| Mode   | When to use                                            | Plan |
|--------|--------------------------------------------------------|------|
| `auto` | Default. Detects new vs committed automatically.       | free (diff) / pro (new) |
| `new`  | Force self-check with auto-trim (Phase 0). Any skill. | pro  |
| `diff` | Force diff against git baseline. Fails if no baseline. | free |

## Oracle Models

| Alias    | API model id         | Use for                                 |
|----------|----------------------|-----------------------------------------|
| `haiku`  | `claude-haiku-5-5`   | Routine CI / pre-commit (default)       |
| `sonnet` | `claude-sonnet-5-5`  | Pre-merge, complex skills               |
| `opus`   | `claude-opus-5-5`    | Maximum fidelity, final sign-off        |

## Exit Codes

| Code | Meaning                        |
|------|--------------------------------|
| `0`  | Passed threshold               |
| `1`  | Below threshold                |
| `2`  | Error (no baseline / API error)|
| `3`  | Pro plan required              |

## Implementation Details

Refer to `.ai/scripts/skill-completeness-check.py` for the full oracle implementation.
Full how-to with all scenarios: `docs/HOWTO-COMPLETENESS-CHECK.md`
