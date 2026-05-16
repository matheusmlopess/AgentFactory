from __future__ import annotations

import logging
from typing import List, Tuple

import anthropic

from .agents import (
    BaseSubAgent,
    ComplianceAgent,
    IntakeAgent,
    SecurityAgent,
    WorkflowAgent,
)
from .context import PipelineMode, SupervisorContext
from .workflow import Workflow, WorkflowStep

logger = logging.getLogger(__name__)


class Supervisor:
    """Hub-and-spoke orchestrator.

    Sub-agents never call each other. Every dispatch returns to the supervisor
    before the next agent is invoked. Remediation re-uses the same pipeline
    with evidence-enriched context — no special code paths.

    Planning pipeline:  Intake → Security → Compliance → Workflow
    Remediation pipeline: Intake → Security → Workflow  (compliance already done)
    """

    def __init__(self, client: anthropic.Anthropic) -> None:
        self.client = client
        self._full_pipeline: List[BaseSubAgent] = [
            IntakeAgent(client),
            SecurityAgent(client),
            ComplianceAgent(client),
            WorkflowAgent(client),
        ]
        self._remediation_pipeline: List[BaseSubAgent] = [
            IntakeAgent(client),
            SecurityAgent(client),
            WorkflowAgent(client),
        ]

    def plan(self, request: str, draft: str = "") -> Tuple[SupervisorContext, Workflow]:
        """Run the full planning pipeline and return context + executable workflow."""
        ctx = SupervisorContext(
            mode=PipelineMode.PLANNING,
            original_request=request,
            draft=draft or request,
        )
        logger.info("supervisor.plan session=%s", ctx.session_id)
        ctx = self._run_pipeline(ctx, self._full_pipeline)
        workflow = self._materialise_workflow(ctx)
        ctx.workflow = workflow.model_dump()
        logger.info(
            "supervisor.plan done steps=%d session=%s", len(workflow.steps), ctx.session_id
        )
        return ctx, workflow

    def remediate(
        self, ctx: SupervisorContext
    ) -> Tuple[SupervisorContext, Workflow]:
        """Re-enter the pipeline with failure evidence for targeted remediation.

        The caller sets ctx.failed_step_ids and ctx.draft (the failure description)
        before invoking this method. The same pipeline agents process the failure
        context and produce a patch workflow containing only replacement steps.
        """
        ctx.mode = PipelineMode.REMEDIATING
        ctx.remediation_round += 1
        logger.info(
            "supervisor.remediate round=%d failed=%s session=%s",
            ctx.remediation_round,
            ctx.failed_step_ids,
            ctx.session_id,
        )
        ctx = self._run_pipeline(ctx, self._remediation_pipeline)
        patch = self._materialise_workflow(ctx)
        logger.info(
            "supervisor.remediate done patch_steps=%d session=%s",
            len(patch.steps),
            ctx.session_id,
        )
        return ctx, patch

    # ------------------------------------------------------------------

    def _run_pipeline(
        self, ctx: SupervisorContext, pipeline: List[BaseSubAgent]
    ) -> SupervisorContext:
        for agent in pipeline:
            name = type(agent).__name__
            logger.info(
                "supervisor: → %s round=%d session=%s", name, ctx.round + 1, ctx.session_id
            )
            ctx = agent.process(ctx)
            logger.info(
                "supervisor: ← %s commands=%d session=%s",
                name,
                len(ctx.commands),
                ctx.session_id,
            )
        return ctx

    def _materialise_workflow(self, ctx: SupervisorContext) -> Workflow:
        raw_steps = (ctx.workflow or {}).get("steps", [])
        steps: List[WorkflowStep] = []
        for i, s in enumerate(raw_steps):
            fallback_id = ctx.commands[i].id if i < len(ctx.commands) else f"step-{i + 1}"
            steps.append(
                WorkflowStep(
                    id=s.get("id", fallback_id),
                    seq=s.get("seq", i + 1),
                    command=s.get("command", ""),
                    type=s.get("type", "shell"),
                    description=s.get("description", ""),
                    security_clearance=s.get("security_clearance", "approved"),
                    remediation_policy=s.get("remediation_policy", "escalate"),
                    max_retries=s.get("max_retries", 1),
                    timeout_seconds=s.get("timeout_seconds", 60),
                    depends_on=s.get("depends_on", []),
                )
            )
        return Workflow(
            session_id=ctx.session_id,
            mode=ctx.mode.value,
            source_request=ctx.original_request,
            steps=steps,
        )
