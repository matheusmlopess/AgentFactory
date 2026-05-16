from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

import anthropic

from .context import CommandStep, SupervisorContext

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# Tool schemas — each agent uses tool_choice to guarantee structured JSON
# ---------------------------------------------------------------------------

_INTAKE_TOOL: Dict = {
    "name": "intake_result",
    "description": "Cleaned draft and extracted shell commands",
    "input_schema": {
        "type": "object",
        "properties": {
            "cleaned_draft": {"type": "string"},
            "commands": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "command": {"type": "string"},
                        "description": {"type": "string"},
                        "type": {"type": "string"},
                    },
                    "required": ["id", "command"],
                },
            },
        },
        "required": ["cleaned_draft", "commands"],
    },
}

_SECURITY_TOOL: Dict = {
    "name": "security_result",
    "description": "Security review findings and blocked command IDs",
    "input_schema": {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "command_id": {"type": "string"},
                        "severity": {"type": "string"},
                        "issue": {"type": "string"},
                        "recommendation": {"type": "string"},
                    },
                    "required": ["command_id", "severity", "issue"],
                },
            },
            "blocked_command_ids": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["findings", "blocked_command_ids"],
    },
}

_COMPLIANCE_TOOL: Dict = {
    "name": "compliance_result",
    "description": "Policy compliance notes, remediation policy overrides, and dependency order",
    "input_schema": {
        "type": "object",
        "properties": {
            "notes": {
                "type": "array",
                "items": {"type": "string"},
            },
            "remediation_policies": {
                "type": "object",
                "description": "command_id → policy override (retry|escalate|skip|abort)",
                "additionalProperties": {"type": "string"},
            },
            "dependency_order": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Command IDs in safe execution order",
            },
        },
        "required": ["notes", "remediation_policies", "dependency_order"],
    },
}

_WORKFLOW_TOOL: Dict = {
    "name": "workflow_result",
    "description": "Final structured workflow steps",
    "input_schema": {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "seq": {"type": "integer"},
                        "command": {"type": "string"},
                        "type": {"type": "string"},
                        "description": {"type": "string"},
                        "security_clearance": {"type": "string"},
                        "remediation_policy": {"type": "string"},
                        "max_retries": {"type": "integer"},
                        "timeout_seconds": {"type": "integer"},
                        "depends_on": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["id", "seq", "command"],
                },
            },
        },
        "required": ["steps"],
    },
}


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class BaseSubAgent(ABC):
    """Sub-agents are pure transforms: they receive context, call Claude,
    and merge their findings back. They never call other agents directly."""

    def __init__(self, client: anthropic.Anthropic) -> None:
        self.client = client

    def process(self, ctx: SupervisorContext) -> SupervisorContext:
        ctx.round += 1
        result = self._call(ctx)
        self._merge(ctx, result)
        return ctx

    def _call_tool(self, system: str, user: str, tool: Dict) -> Dict:
        resp = self.client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
        )
        for block in resp.content:
            if block.type == "tool_use":
                return block.input  # type: ignore[return-value]
        return {}

    @abstractmethod
    def _call(self, ctx: SupervisorContext) -> Dict[str, Any]: ...

    @abstractmethod
    def _merge(self, ctx: SupervisorContext, result: Dict[str, Any]) -> None: ...


# ---------------------------------------------------------------------------
# Concrete agents
# ---------------------------------------------------------------------------


class IntakeAgent(BaseSubAgent):
    """Round 1 — Clean the draft and extract Linux/shell commands."""

    _SYSTEM = (
        "You are an intake processor for a Linux automation system. "
        "Given a user request or remediation draft, clean the text and extract "
        "every distinct Linux/shell command. Assign each command a short kebab-case id. "
        "In remediation mode, focus only on commands that fix the reported failures."
    )

    def _call(self, ctx: SupervisorContext) -> Dict:
        user = f"Context:\n{ctx.to_brief()}\n\nDraft:\n{ctx.draft}"
        return self._call_tool(self._SYSTEM, user, _INTAKE_TOOL)

    def _merge(self, ctx: SupervisorContext, result: Dict) -> None:
        ctx.draft = result.get("cleaned_draft", ctx.draft)
        ctx.commands = [
            CommandStep(
                id=c["id"],
                command=c["command"],
                description=c.get("description", ""),
                type=c.get("type", "shell"),
            )
            for c in result.get("commands", [])
        ]


class SecurityAgent(BaseSubAgent):
    """Round 2 — Security review and validation of extracted commands."""

    _SYSTEM = (
        "You are a Linux security validator. Review the provided commands for "
        "security risks: privilege escalation, destructive operations without guards, "
        "injection vectors, insecure network calls, or policy violations. "
        "Classify findings by severity (critical|high|medium|low) and identify which "
        "commands must be blocked."
    )

    def _call(self, ctx: SupervisorContext) -> Dict:
        cmds = [{"id": c.id, "command": c.command} for c in ctx.commands]
        user = (
            f"Context:\n{ctx.to_brief()}\n\n"
            f"Commands to review:\n{json.dumps(cmds, indent=2)}"
        )
        return self._call_tool(self._SYSTEM, user, _SECURITY_TOOL)

    def _merge(self, ctx: SupervisorContext, result: Dict) -> None:
        ctx.security_findings = result.get("findings", [])
        ctx.blocked_commands = result.get("blocked_command_ids", [])
        ctx.commands = [c for c in ctx.commands if c.id not in ctx.blocked_commands]


class ComplianceAgent(BaseSubAgent):
    """Round 3 — Policy compliance, idempotency checks, and dependency ordering."""

    _SYSTEM = (
        "You are a Linux operations compliance checker. Given a set of shell commands, "
        "verify: idempotency (can each be safely re-run?), execution order "
        "(data-dependency and ordering constraints), and appropriate remediation policies "
        "(should failures retry, escalate to supervisor, skip, or abort?). "
        "Return ordered command IDs and per-command remediation policy overrides."
    )

    def _call(self, ctx: SupervisorContext) -> Dict:
        cmds = [{"id": c.id, "command": c.command} for c in ctx.commands]
        user = (
            f"Context:\n{ctx.to_brief()}\n\n"
            f"Security findings: {len(ctx.security_findings)}, "
            f"blocked: {len(ctx.blocked_commands)}\n\n"
            f"Approved commands:\n{json.dumps(cmds, indent=2)}"
        )
        return self._call_tool(self._SYSTEM, user, _COMPLIANCE_TOOL)

    def _merge(self, ctx: SupervisorContext, result: Dict) -> None:
        ctx.compliance_notes = result.get("notes", [])
        policies = result.get("remediation_policies", {})
        dep_order = result.get("dependency_order", [])
        for cmd in ctx.commands:
            if cmd.id in policies:
                cmd.remediation_policy = policies[cmd.id]
        if dep_order:
            order_index = {cid: i for i, cid in enumerate(dep_order)}
            ctx.commands.sort(key=lambda c: order_index.get(c.id, 999))


class WorkflowAgent(BaseSubAgent):
    """Round 4 — Structure approved commands into the final executable JSON workflow."""

    _SYSTEM = (
        "You are a workflow formatter. Convert a validated, ordered list of Linux commands "
        "into a structured executable workflow. Assign sequential step numbers, set "
        "appropriate timeouts (simple cmds: 30s, package installs: 120s, builds: 300s), "
        "and wire depends_on relationships. In remediation mode, only include replacement "
        "steps for the failed ones, using seq numbers that slot into the existing workflow."
    )

    def _call(self, ctx: SupervisorContext) -> Dict:
        cmds = [
            {
                "id": c.id,
                "command": c.command,
                "description": c.description,
                "remediation_policy": c.remediation_policy,
            }
            for c in ctx.commands
        ]
        user = (
            f"Context:\n{ctx.to_brief()}\n\n"
            f"Validated commands:\n{json.dumps(cmds, indent=2)}"
        )
        return self._call_tool(self._SYSTEM, user, _WORKFLOW_TOOL)

    def _merge(self, ctx: SupervisorContext, result: Dict) -> None:
        ctx.workflow = result
