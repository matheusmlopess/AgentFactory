from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class PipelineMode(str, Enum):
    PLANNING = "planning"
    EXECUTING = "executing"
    REMEDIATING = "remediating"


@dataclass
class CommandStep:
    id: str
    command: str
    type: str = "shell"
    description: str = ""
    remediation_policy: str = "escalate"  # retry|escalate|skip|abort
    max_retries: int = 1
    timeout_seconds: int = 60
    depends_on: List[str] = field(default_factory=list)


@dataclass
class Evidence:
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


@dataclass
class SupervisorContext:
    """Shared state envelope that flows through every agent in the pipeline.

    Each sub-agent receives this, enriches it, and returns it to the supervisor.
    The supervisor never passes context directly between agents — everything
    routes back through the hub before the next dispatch.
    """

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    round: int = 0
    mode: PipelineMode = PipelineMode.PLANNING
    original_request: str = ""
    draft: str = ""
    commands: List[CommandStep] = field(default_factory=list)
    security_findings: List[Dict[str, Any]] = field(default_factory=list)
    blocked_commands: List[str] = field(default_factory=list)
    compliance_notes: List[str] = field(default_factory=list)
    workflow: Optional[Dict[str, Any]] = None
    evidence: List[Evidence] = field(default_factory=list)
    failed_step_ids: List[str] = field(default_factory=list)
    remediation_round: int = 0

    def to_brief(self) -> str:
        """Compact multi-line summary passed as context to each sub-agent."""
        lines = [
            f"session={self.session_id} round={self.round} mode={self.mode.value}",
            f"request={self.original_request[:200]}",
        ]
        if self.commands:
            lines.append(f"commands=[{', '.join(c.id for c in self.commands)}]")
        if self.security_findings:
            lines.append(f"security_findings={len(self.security_findings)} issues")
        if self.blocked_commands:
            lines.append(f"blocked={self.blocked_commands}")
        if self.evidence:
            failed = [e for e in self.evidence if not e.succeeded]
            lines.append(
                f"evidence={len(self.evidence)} steps, {len(failed)} failed"
            )
        if self.failed_step_ids:
            lines.append(f"failed_steps={self.failed_step_ids}")
        return "\n".join(lines)
