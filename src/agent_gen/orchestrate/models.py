"""Orchestration data models.

Ported from the unmerged supervisor-agent-harness branch
(src/agent_gen/supervisor/{workflow,context}.py) with pydantic re-expressed
as stdlib dataclasses and the step model extended for the orchestration
contract (type: shell|agent|delegate, agent, prompt, expects).

No imports from click or cli.py — this subpackage is the programmatic API
surface consumed by external harnesses.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

STEP_TYPES = ("shell", "agent", "delegate")
REMEDIATION_POLICIES = ("retry", "escalate", "skip", "abort")

# Synthetic exit codes (never produced by the child process itself)
EXIT_TIMEOUT = 124       # POSIX timeout convention (ported)
EXIT_EXPECTS_FAILED = 125  # output failed the step's `expects` validation
                           # (also used for empty-output / provider-error agent responses)

_TEMPLATE_RE = re.compile(r"\{steps\.([\w./-]+)\.(stdout|stderr|exit_code)\}")
_TEMPLATE_TRUNCATE = 8_000  # cap per-substitution to prevent prompt blowup


class StepStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass
class Evidence:
    """Immutable record of one step attempt. Ported ~verbatim."""

    step_id: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    attempt: int = 1

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkflowStep:
    """One unit of work. type decides the runner:

    shell    → command executed via the shell
    agent    → prompt sent to a CLI agent from the contract's agents table
    delegate → prompt sent to the supervisor agent, whose JSON reply is
               validated and spliced in as new steps (PR3)
    """

    id: str = field(default_factory=lambda: f"step-{uuid.uuid4().hex[:8]}")
    seq: int = 0
    type: str = "shell"
    command: str = ""            # shell steps
    agent: str = ""              # agent/delegate steps; "" = contract default
    prompt: str = ""             # agent/delegate steps
    description: str = ""
    expects: str = ""            # "" | nonempty | json | regex:<pattern>
    security_clearance: str = "approved"   # approved|conditional|blocked
    remediation: str = "escalate"          # retry|escalate|skip|abort
    max_retries: int = 1
    timeout_seconds: int = 60
    depends_on: list[str] = field(default_factory=list)
    evidence_capture: dict = field(
        default_factory=lambda: {"stdout": True, "stderr": True, "exit_code": True}
    )

    @classmethod
    def from_dict(cls, data: dict, *, seq: int = 0) -> "WorkflowStep":
        known = {f for f in cls.__dataclass_fields__}  # noqa: C401
        unknown = set(data) - known - {"remediation_policy"}
        if unknown:
            raise ValueError(f"step has unknown field(s): {sorted(unknown)}")
        payload = dict(data)
        # Accept the branch-era field name as an alias
        if "remediation_policy" in payload and "remediation" not in payload:
            payload["remediation"] = payload.pop("remediation_policy")
        payload.setdefault("seq", seq)
        step = cls(**payload)
        step.validate()
        return step

    def validate(self) -> None:
        if self.type not in STEP_TYPES:
            raise ValueError(f"step '{self.id}': unknown type '{self.type}'")
        if self.remediation not in REMEDIATION_POLICIES:
            raise ValueError(
                f"step '{self.id}': unknown remediation '{self.remediation}'"
            )
        if self.type == "shell" and not self.command:
            raise ValueError(f"step '{self.id}': shell step requires 'command'")
        if self.type in ("agent", "delegate") and not self.prompt:
            raise ValueError(f"step '{self.id}': {self.type} step requires 'prompt'")
        if self.expects and self.expects not in ("nonempty", "json") and not self.expects.startswith("regex:"):
            raise ValueError(
                f"step '{self.id}': expects must be nonempty|json|regex:<pattern>"
            )

    def render_prompt(self, evidence_by_step: dict[str, Evidence]) -> str:
        """Substitute {steps.<id>.stdout|stderr|exit_code} placeholders."""

        def _sub(match: re.Match) -> str:
            step_id, attr = match.group(1), match.group(2)
            ev = evidence_by_step.get(step_id)
            if ev is None:
                return match.group(0)  # leave unresolved references visible
            value = str(getattr(ev, attr))
            return value[:_TEMPLATE_TRUNCATE]

        return _TEMPLATE_RE.sub(_sub, self.prompt)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Workflow:
    """A named, versioned plan of steps. Ported; patch() semantics kept."""

    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    mode: str = ""  # "" = use contract default_mode
    workflow_id: str = field(default_factory=lambda: f"wf-{uuid.uuid4().hex[:12]}")
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    steps: list[WorkflowStep] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Workflow":
        payload = dict(data)
        raw_steps = payload.pop("steps", [])
        wf = cls(**{k: v for k, v in payload.items() if k in cls.__dataclass_fields__})
        wf.steps = [
            WorkflowStep.from_dict(s, seq=i * 10) if isinstance(s, dict) else s
            for i, s in enumerate(raw_steps, start=1)
        ]
        wf.validate()
        return wf

    def validate(self) -> None:
        if not self.name:
            raise ValueError("workflow requires a 'name'")
        ids = [s.id for s in self.steps]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate step id(s): {sorted(dupes)}")
        known = set(ids)
        for s in self.steps:
            for dep in s.depends_on:
                if dep not in known:
                    raise ValueError(
                        f"step '{s.id}': depends_on unknown step '{dep}'"
                    )
        for s in self.steps:
            s.validate()

    def patch(
        self, replacement_steps: list[WorkflowStep], failed_ids: list[str]
    ) -> "Workflow":
        """Return a new Workflow with failed steps replaced by remediated ones.

        Kept steps retain their original sequence numbers; replacements are
        inserted and the combined list re-sorted by seq. (Ported verbatim.)
        """
        kept = [s for s in self.steps if s.id not in failed_ids]
        merged = kept + replacement_steps
        merged.sort(key=lambda s: s.seq)
        clone = Workflow(
            name=self.name,
            version=self.version,
            description=self.description,
            mode=self.mode,
            workflow_id=self.workflow_id,
            created_at=self.created_at,
            steps=merged,
        )
        return clone

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "mode": self.mode,
            "workflow_id": self.workflow_id,
            "created_at": self.created_at,
            "steps": [s.to_dict() for s in self.steps],
        }


@dataclass
class RunResult:
    """Machine-readable outcome of one orchestration run (the --json surface)."""

    workflow_name: str
    workflow_id: str
    mode: str
    run_id: str = field(default_factory=lambda: f"run-{uuid.uuid4().hex[:12]}")
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    finished_at: str = ""
    statuses: dict[str, str] = field(default_factory=dict)  # step_id → StepStatus value
    evidence: list[Evidence] = field(default_factory=list)
    workflow_snapshot: Optional[dict] = None  # final workflow incl. spliced steps

    @property
    def ok(self) -> bool:
        return bool(self.statuses) and all(
            s in (StepStatus.SUCCESS.value, StepStatus.SKIPPED.value)
            for s in self.statuses.values()
        )

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "workflow_name": self.workflow_name,
            "workflow_id": self.workflow_id,
            "mode": self.mode,
            "ok": self.ok,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "statuses": self.statuses,
            "evidence": [e.to_dict() for e in self.evidence],
            "workflow_snapshot": self.workflow_snapshot,
        }


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_workflow(path: str | Path) -> Workflow:
    """Load a workflow from <name>.workflow.json or a Markdown wrapper.

    Markdown wrapper: flat `key: value` frontmatter (name, version,
    description, mode — same dialect as SKILL.md) plus one fenced ```json
    block containing {"steps": [...]}.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"workflow not found: {p}")
    text = p.read_text(encoding="utf-8")

    if p.suffix == ".json" or p.name.endswith(".workflow.json"):
        return Workflow.from_dict(json.loads(text))

    if p.suffix == ".md":
        meta = _parse_flat_frontmatter(text)
        block = _first_json_fence(text)
        if block is None:
            raise ValueError(f"{p}: no ```json block with steps found")
        data = json.loads(block)
        for key in ("name", "version", "description", "mode"):
            if key in meta and key not in data:
                data[key] = meta[key]
        return Workflow.from_dict(data)

    raise ValueError(f"{p}: unsupported workflow format (use .workflow.json or .md)")


def _parse_flat_frontmatter(text: str) -> dict:
    """Flat `key: value` frontmatter — same dialect the Librarian uses for SKILL.md."""
    content = text.lstrip()
    if not content.startswith("---"):
        return {}
    try:
        end = content.index("---", 3)
    except ValueError:
        return {}
    result: dict = {}
    for line in content[3:end].splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        if key.strip():
            result[key.strip()] = value.strip()
    return result


def _first_json_fence(text: str) -> str | None:
    match = re.search(r"```json\s*\n(.*?)```", text, flags=re.DOTALL)
    return match.group(1) if match else None


def validate_workflow_data(data: Any) -> list[str]:
    """Contract-schema validation returning a list of issues (empty = valid).

    Used by `orchestrate validate` and (PR4) by the Librarian audit.
    """
    issues: list[str] = []
    if not isinstance(data, dict):
        return ["workflow root must be a JSON object"]
    try:
        Workflow.from_dict(data)
    except (ValueError, TypeError) as exc:
        issues.append(str(exc))
    return issues
