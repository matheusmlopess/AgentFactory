from __future__ import annotations

from datetime import datetime, timezone
from typing import List
import uuid

from pydantic import BaseModel, Field


class EvidenceCapture(BaseModel):
    stdout: bool = True
    stderr: bool = True
    exit_code: bool = True


class WorkflowStep(BaseModel):
    id: str = Field(default_factory=lambda: f"step-{uuid.uuid4().hex[:8]}")
    seq: int
    command: str
    type: str = "shell"
    description: str = ""
    security_clearance: str = "approved"  # approved|conditional|blocked
    remediation_policy: str = "escalate"  # retry|escalate|skip|abort
    max_retries: int = 1
    timeout_seconds: int = 60
    depends_on: List[str] = Field(default_factory=list)
    evidence_capture: EvidenceCapture = Field(default_factory=EvidenceCapture)


class RemediationConfig(BaseModel):
    on_step_failure: str = "escalate_to_supervisor"
    max_remediation_rounds: int = 2


class Workflow(BaseModel):
    workflow_id: str = Field(default_factory=lambda: f"wf-{uuid.uuid4().hex[:12]}")
    session_id: str = ""
    version: str = "1"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    mode: str = "planning"
    source_request: str = ""
    steps: List[WorkflowStep] = Field(default_factory=list)
    remediation: RemediationConfig = Field(default_factory=RemediationConfig)

    def patch(
        self, replacement_steps: List[WorkflowStep], failed_ids: List[str]
    ) -> "Workflow":
        """Return a new Workflow with failed steps replaced by remediated ones.

        Kept steps retain their original sequence numbers; replacement steps
        are inserted and the combined list is re-sorted by seq.
        """
        kept = [s for s in self.steps if s.id not in failed_ids]
        merged = kept + replacement_steps
        merged.sort(key=lambda s: s.seq)
        return self.model_copy(update={"steps": merged, "mode": "remediating"})
