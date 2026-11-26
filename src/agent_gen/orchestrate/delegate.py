"""Delegate-step planning: a supervisor CLI agent turns a task into substeps (orchestrate PR3, #196).

The contract's `supervisor_agent` (claude by default) receives the task plus a strict reply format: a JSON array of
steps. The reply is parsed (code fences stripped), every substep is validated like any workflow step, and the
plan is checked against the contract before anything runs:

* shell substeps need both `policies.allow_shell_steps` and `policies.delegate_shell_steps` (off by default: a
  model-written shell command never runs unless the project opts in);
* nested delegate substeps are allowed only below `policies.max_delegate_depth`;
* at most `policies.max_delegate_steps` (default 12) substeps;
* substep ids are prefixed with the delegate's id, so they never collide with the rest of the workflow.

A reply that does not parse gets one re-prompt with the error; after that the delegate step fails and its
remediation policy applies. `escalate` remediation uses the same planner with a failure draft and replaces the
failed step with the plan.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from .models import STEP_TYPES, Evidence, WorkflowStep


class DelegateError(Exception):
    """The supervisor could not produce a usable plan; the message says why."""


class DelegateUnavailable(DelegateError):
    """No supervisor can be asked (agent missing/disabled, or the call itself failed)."""


AskFn = Callable[[str, int], Evidence]  # (planner prompt, attempt) -> evidence of the supervisor call

_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)```", re.DOTALL)
_ID_SAFE = re.compile(r"[^a-z0-9_-]+")

PLAN_INSTRUCTIONS = """You are the supervisor of an AgentFactory workflow. Plan the task below as workflow steps.

Reply with ONLY a JSON array (no prose before or after). Each element is one step:
  {{"id": "short-kebab-id", "type": "shell" | "agent"{nested},
    "command": "<shell command>"            (shell steps),
    "prompt": "<instruction>", "agent": "<optional CLI agent: {agents}>"   (agent steps),
    "depends_on": ["<earlier id>"], "expects": "nonempty" | "json" | "regex:<pattern>",
    "remediation": "retry" | "skip" | "abort", "max_retries": 1}}
{shell_rule}Use at most {limit} steps. Steps run in array order.

TASK:
{task}
"""


def _instructions(task: str, contract, depth: int) -> str:
    policies = contract.policies
    nested_ok = depth + 1 < int(policies.get("max_delegate_depth", 1))
    agents = ", ".join(sorted(n for n, s in contract.agents.items() if s.get("enabled", True) and n != "harness"))
    return PLAN_INSTRUCTIONS.format(
        nested=' | "delegate"' if nested_ok else "",
        agents=agents or "claude",
        shell_rule="" if _shell_allowed(policies) else "Do NOT use shell steps: they are disabled.\n",
        limit=int(policies.get("max_delegate_steps", 12)),
        task=task,
    )


def _shell_allowed(policies: dict) -> bool:
    return bool(policies.get("allow_shell_steps", True) and policies.get("delegate_shell_steps", False))


def parse_plan(raw: str) -> list[dict]:
    """The JSON array from a supervisor reply (fenced or bare); `{"steps": [...]}` is accepted too."""
    text = raw.strip()
    fenced = _FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    elif not text.startswith(("[", "{")):
        start = min((i for i in (text.find("["), text.find("{")) if i >= 0), default=-1)
        if start < 0:
            raise DelegateError("reply contains no JSON")
        text = text[start:]
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise DelegateError(f"reply is not valid JSON: {exc}") from None
    if isinstance(data, dict) and isinstance(data.get("steps"), list):
        data = data["steps"]
    if not isinstance(data, list) or not all(isinstance(s, dict) for s in data):
        raise DelegateError("reply must be a JSON array of step objects")
    return data


def build_substeps(raw_steps: list[dict], parent: WorkflowStep, contract, depth: int) -> list[WorkflowStep]:
    """Validate a parsed plan against the contract and return steps ready to splice."""
    policies = contract.policies
    limit = int(policies.get("max_delegate_steps", 12))
    if len(raw_steps) > limit:
        raise DelegateError(f"plan has {len(raw_steps)} steps; the limit is {limit} (policies.max_delegate_steps)")
    prefix = f"{parent.id}-"
    renamed: dict[str, str] = {}
    for i, raw in enumerate(raw_steps, start=1):
        base = _ID_SAFE.sub("-", str(raw.get("id") or f"step{i}").lower()).strip("-") or f"step{i}"
        renamed[str(raw.get("id", base))] = base if base.startswith(prefix) else prefix + base
    steps = []
    for raw in raw_steps:
        data = dict(raw)
        data["id"] = renamed[str(raw.get("id", ""))] if str(raw.get("id", "")) in renamed else prefix + "step"
        data["depends_on"] = [renamed.get(str(d), str(d)) for d in data.get("depends_on", [])]
        data.setdefault("type", "agent" if "prompt" in data else "shell")
        if data["type"] not in STEP_TYPES:
            raise DelegateError(f"substep '{data['id']}': unknown type '{data['type']}'")
        if data["type"] == "shell" and not _shell_allowed(policies):
            raise DelegateError(
                f"substep '{data['id']}' is a shell step; planned shell steps need policies.delegate_shell_steps"
            )
        if data["type"] == "delegate" and depth + 1 >= int(policies.get("max_delegate_depth", 1)):
            raise DelegateError(f"substep '{data['id']}' delegates again, past policies.max_delegate_depth")
        try:
            step = WorkflowStep.from_dict(data, seq=parent.seq)
        except (ValueError, TypeError) as exc:
            raise DelegateError(f"substep '{data['id']}': {exc}") from None
        steps.append(step)
    ids = [s.id for s in steps]
    if len(set(ids)) != len(ids):
        raise DelegateError(f"plan repeats step ids {sorted({i for i in ids if ids.count(i) > 1})}")
    return steps


def plan_substeps(
    step: WorkflowStep,
    task: str,
    contract,
    evidence: list[Evidence],
    depth: int = 0,
    ask: AskFn | None = None,
) -> list[WorkflowStep]:
    """Ask the supervisor to plan *task* and return validated substeps (one re-prompt on a bad reply)."""
    if ask is None:
        raise DelegateUnavailable(f"step '{step.id}': no supervisor runner was provided")
    prompt = _instructions(task, contract, depth)
    last_error = ""
    for attempt in (1, 2):
        ev = ask(prompt, attempt)
        if not ev.succeeded:
            raise DelegateUnavailable(
                f"supervisor call for step '{step.id}' failed (exit {ev.exit_code}): {ev.stderr.strip()[:300]}"
            )
        try:
            return build_substeps(parse_plan(ev.stdout), step, contract, depth)
        except DelegateError as exc:
            last_error = str(exc)
            prompt = (
                f"{_instructions(task, contract, depth)}\nYour previous reply was rejected: {last_error}\n"
                "Reply again with ONLY the JSON array."
            )
    raise DelegateError(f"supervisor plan for step '{step.id}' rejected twice: {last_error}")


def _failure_draft(step: WorkflowStep, evidence: list[Evidence]) -> str:
    """Build a remediation draft from the most recent failure evidence. (Ported.)"""
    failed_ev = next((e for e in reversed(evidence) if e.step_id == step.id), None)
    lines = [
        "A workflow step failed. Plan replacement steps that achieve the same goal.",
        f"Failed step: {step.command or step.prompt}",
    ]
    if failed_ev:
        lines.append(f"Exit code: {failed_ev.exit_code}")
        if failed_ev.stderr:
            lines.append(f"Stderr:\n{failed_ev.stderr[:1000]}")
        if failed_ev.stdout:
            lines.append(f"Stdout:\n{failed_ev.stdout[:500]}")
    return "\n".join(lines)
