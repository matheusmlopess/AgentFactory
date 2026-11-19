"""The canonical CRAFT plan format (`craft-plan/0.1`, CRAFT ADR 0002) ⇄ AgentFactory workflows (#194).

`orchestrate` keeps `Workflow` / `WorkflowStep` as its internal model. This module reads and writes the shared
format so plans can move between the harness, the webapp, Twinwork and AgentFactory. Rules (ADR 0002 acceptance):

* `version` is the format tag `craft-plan/0.1`; the plan's own revision travels in `x-af.version`.
* Keys starting with `x-` (root and step) are ignored by the executor and preserved on a round trip
  (e.g. the harness's `x-studio` canvas layout). Any other unknown key is an error, so typos are caught.
* Step ids match `^[a-z0-9_-]+$`.
* `provider: anthropic|openai` steps load, and the CLI executor refuses them when they run.
* `seq`, `workflow_id` and `created_at` are run/internal data, not part of a plan.
* The canonical agent name `agy` is AgentFactory's `antigravity` contract entry.
"""

from __future__ import annotations

import re
from dataclasses import fields
from typing import Any

from .models import PROVIDERS, REMEDIATION_POLICIES, STEP_TYPES, Workflow, WorkflowStep

FORMAT = "craft-plan/0.1"
CLEARANCES = ("approved", "conditional", "blocked")
_STEP_ID_RE = re.compile(r"^[a-z0-9_-]+$")
_ROOT_FIELDS = {"version", "name", "description", "mode", "steps"}
_STEP_FIELDS = {
    "id", "type", "description", "command", "agent", "provider", "model", "prompt", "depends_on", "expects",
    "remediation", "max_retries", "timeout_seconds", "security_clearance", "evidence_capture",
}  # fmt: skip
_AGENT_TO_CANONICAL = {"antigravity": "agy"}
_AGENT_FROM_CANONICAL = {v: k for k, v in _AGENT_TO_CANONICAL.items()}
_STEP_DEFAULTS = {f.name: f.default for f in fields(WorkflowStep) if not callable(f.default)}


def is_canonical(data: Any) -> bool:
    return isinstance(data, dict) and data.get("version") == FORMAT


def _is_ext(key: str) -> bool:
    return key.startswith("x-")


def canonical_issues(data: Any) -> list[str]:
    """Schema problems in a canonical plan (empty = valid). Mirrors contracts/orchestration-plan.schema.json."""
    if not isinstance(data, dict):
        return ["plan root must be a JSON object"]
    issues: list[str] = []
    if data.get("version") != FORMAT:
        issues.append(f"version must be '{FORMAT}'")
    if not isinstance(data.get("name"), str) or not data.get("name"):
        issues.append("plan requires a non-empty 'name'")
    unknown = sorted(k for k in data if k not in _ROOT_FIELDS and not _is_ext(k))
    if unknown:
        issues.append(f"unknown root field(s): {unknown} (extensions must start with 'x-')")
    steps = data.get("steps")
    if not isinstance(steps, list):
        return [*issues, "'steps' must be an array"]
    for i, step in enumerate(steps):
        where = f"steps[{i}]"
        if not isinstance(step, dict):
            issues.append(f"{where}: must be an object")
            continue
        sid = step.get("id")
        if not isinstance(sid, str) or not _STEP_ID_RE.fullmatch(sid):
            issues.append(f"{where}: id {sid!r} must match ^[a-z0-9_-]+$")
        else:
            where = f"step '{sid}'"
        if step.get("type") not in STEP_TYPES:
            issues.append(f"{where}: type must be one of {list(STEP_TYPES)}")
        unknown = sorted(k for k in step if k not in _STEP_FIELDS and not _is_ext(k))
        if unknown:
            issues.append(f"{where}: unknown field(s) {unknown}")
        for key, allowed in (("provider", PROVIDERS[1:]), ("remediation", REMEDIATION_POLICIES),
                             ("security_clearance", CLEARANCES)):  # fmt: skip
            if key in step and step[key] not in allowed:
                issues.append(f"{where}: {key} must be one of {list(allowed)}")
        issues.extend(
            f"{where}: {key} must be a non-negative integer"
            for key in ("max_retries", "timeout_seconds")
            if key in step and (not isinstance(step[key], int) or isinstance(step[key], bool) or step[key] < 0)
        )
        deps = step.get("depends_on", [])
        if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            issues.append(f"{where}: depends_on must be an array of step ids")
    return issues


def from_canonical(data: dict) -> Workflow:
    """Build a Workflow from a canonical plan; raises ValueError listing every schema problem."""
    issues = canonical_issues(data)
    if issues:
        raise ValueError("invalid craft-plan/0.1: " + "; ".join(issues))
    root_ext = {k: v for k, v in data.items() if _is_ext(k)}
    af_ext = root_ext.pop("x-af", {}) or {}
    steps = []
    for raw in data["steps"]:
        step = {k: v for k, v in raw.items() if k in _STEP_FIELDS}
        if step.get("agent") in _AGENT_FROM_CANONICAL:
            step["agent"] = _AGENT_FROM_CANONICAL[step["agent"]]
        ext = {k: v for k, v in raw.items() if _is_ext(k)}
        if ext:
            step["extensions"] = ext
        steps.append(step)
    payload: dict[str, Any] = {
        "name": data["name"],
        "description": data.get("description", ""),
        "mode": data.get("mode", ""),
        "steps": steps,
        "extensions": root_ext,
    }
    if isinstance(af_ext, dict) and af_ext.get("version"):
        payload["version"] = af_ext["version"]
    return Workflow.from_dict(payload)


def to_canonical(workflow: Workflow) -> dict:
    """Serialize a Workflow as a canonical plan. Raises ValueError for step ids the format does not allow."""
    bad = [s.id for s in workflow.steps if not _STEP_ID_RE.fullmatch(s.id)]
    if bad:
        raise ValueError(f"step id(s) {bad} must match ^[a-z0-9_-]+$ to be written as {FORMAT}")
    out: dict[str, Any] = {"version": FORMAT, "name": workflow.name}
    if workflow.description:
        out["description"] = workflow.description
    if workflow.mode:
        out["mode"] = workflow.mode
    steps = []
    for s in workflow.steps:
        explicit = getattr(s, "_explicit_fields", None)
        d: dict[str, Any] = {"id": s.id, "type": s.type}
        for key in ("description", "command", "agent", "provider", "model", "prompt", "expects"):
            value = getattr(s, key)
            if value:
                d[key] = _AGENT_TO_CANONICAL.get(value, value) if key == "agent" else value
        if s.depends_on:
            d["depends_on"] = list(s.depends_on)
        for key in ("remediation", "max_retries", "timeout_seconds", "security_clearance"):
            value = getattr(s, key)
            # Keep fields the plan set; fields left to contract policies stay unset so policies still apply.
            if (explicit is not None and key in explicit) or (explicit is None and value != _STEP_DEFAULTS[key]):
                d[key] = value
        if s.evidence_capture != {"stdout": True, "stderr": True, "exit_code": True}:
            d["evidence_capture"] = dict(s.evidence_capture)
        d.update(s.extensions)
        steps.append(d)
    out["steps"] = steps
    out["x-af"] = {"version": workflow.version}
    out.update(workflow.extensions)
    return out
