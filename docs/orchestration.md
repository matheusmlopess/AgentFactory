# Orchestration guide
<!-- version: 1.0.0 -->

`agentfactory-gen orchestrate` runs **workflows**: ordered or parallel steps executed by shell commands and CLI
agents (claude, codex, agy), with evidence for every step. Design notes: `docs/DECISIONS-ORCHESTRATION.md`.

## Quick start

```bash
agentfactory-gen orchestrate init                 # writes .ai/config/orchestration.json (the contract)
agentfactory-gen orchestrate list                 # project workflows and the ones agents ship
agentfactory-gen orchestrate validate release     # schema + dependency + cycle checks; names the dialect
agentfactory-gen orchestrate run release --dry-run
agentfactory-gen orchestrate run release          # evidence → .ai/memory/orchestration-runs/<ts>-release/
```

A workflow argument is a path, a bare name (`.ai/orchestration/workflows/<name>.*`) or `<agent>/<name>`
(a workflow inside a Portable Unit: `.ai/agents/<agent>/orchestration/workflows/<name>.*`).

## Workflow files

| File | Dialect |
|---|---|
| `<name>.workflow.json` | AgentFactory workflow |
| `<name>.plan.json` | shared CRAFT plan `craft-plan/0.1` (also used by the harness and the webapp) |
| `<name>.md` | frontmatter (`name`, `version`, `description`, `mode`) + one ```json block with `{"steps": [...]}` |

`orchestrate convert <wf> --to canonical|af [-o FILE]` converts between the two JSON dialects.

```json
{ "name": "release", "mode": "dag",
  "steps": [
    {"id": "lint", "type": "shell", "command": "ruff check src", "remediation": "retry", "max_retries": 2},
    {"id": "test", "type": "shell", "command": "pytest -q"},
    {"id": "notes", "type": "agent", "agent": "claude", "model": "sonnet",
     "prompt": "Write release notes from:\n{steps.test.stdout}", "depends_on": ["lint", "test"],
     "expects": "nonempty"}]}
```

Step fields: `type` (`shell` | `agent` | `delegate`), `command`, `agent`, `model`, `prompt` (with
`{steps.<id>.stdout|stderr|exit_code}`), `depends_on`, `expects` (`nonempty` | `json` | `regex:<p>`),
`remediation` (`retry` | `skip` | `abort` | `escalate`), `max_retries`, `timeout_seconds`, `security_clearance`.
Fields left out take the contract's `policies`.

## Modes

| Mode | Use it for |
|---|---|
| `sequential` (default) | steps in order; full remediation incl. `escalate` |
| `dag` | independent steps in parallel (`policies.max_parallel`); a failed dependency blocks its dependents |
| `checkpoint` | a human approves each step after the first; unapproved runs pause (exit code 3) and continue with `orchestrate run --resume <run-id>`; `--yes` approves all |

Pick with `"mode"` in the file or `--mode` on the command line.

## Supervisor steps

* `"type": "delegate"`: the contract's `supervisor_agent` turns the step prompt into steps, which run in place.
* `"remediation": "escalate"`: a failed step is re-planned from its evidence and replaced.
* Planned shell commands run only with `policies.delegate_shell_steps: true`. Use `checkpoint` mode to review plans.
* `"agent": "harness"` with a workflow name as the prompt runs that workflow as a child, at most
  `policies.max_delegate_depth` levels deep.

## The contract (`.ai/config/orchestration.json`)

Merged over built-in defaults. Per agent: `invocation` (with `{prompt}`), `model_args`, `env_unset`, `stdin`,
`enabled`. Claude runs on your Claude subscription by default (`env_unset` drops `ANTHROPIC_API_KEY`;
`AGENTFACTORY_CLAUDE_BACKEND=api` keeps it). Policies: `default_remediation`, `max_retries`, `timeout_seconds`,
`max_remediation_rounds`, `max_parallel`, `max_delegate_depth`, `max_delegate_steps`, `allow_shell_steps`,
`delegate_shell_steps`, `empty_output_is_failure`.

## Workflows in Portable Units

Put workflows in `<agent>/orchestration/workflows/`. `audit --fix` sets `orchestration_plan` to the first
workflow and warns about workflows that do not load. `import` lists workflows with shell steps next to scripts
and asks before installing them (`--allow-scripts` skips the question, `--dry-run` previews).

## Evidence and exit codes

Every attempt writes `steps/<id>-<attempt>.stdout|stderr`, and each run writes `run.json`. Exit codes: `0` OK,
`1` failed, `3` paused (checkpoint). Step-level codes in the evidence: `124` timeout, `125` `expects` or a
provider error, `126` refused by policy.

## Live checks

`pytest -m live src/tests/test_orchestrate_live.py` runs a one-step workflow against each installed CLI and
skips the ones that are missing or out of quota.
