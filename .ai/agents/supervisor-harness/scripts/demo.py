#!/usr/bin/env python3
"""
Supervisor Harness — Scenario Demonstrations
============================================

Renders nine pipeline scenarios with box-drawing traces showing:

  · Planning pipeline  (hub-and-spoke: every agent returns to supervisor)
  · JSON workflow      (emitted steps)
  · Execution trace    (per-step evidence + policy outcomes)
  · Remediation loops  (failure → supervisor → patch → re-execute)

No real API calls or shell commands are made.

Usage:
    python demo.py              all 9 scenarios
    python demo.py 1 3 6        specific scenarios by number
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

from agent_gen.supervisor.context import (
    CommandStep,
    Evidence,
    PipelineMode,
    SupervisorContext,
)
from agent_gen.supervisor.harness import HarnessRunner
from agent_gen.supervisor.workflow import Workflow, WorkflowStep

# ─── Layout ───────────────────────────────────────────────────────────────────

W = 82  # total box width


# ─── Mock helpers ─────────────────────────────────────────────────────────────


def _proc(exit_code: int = 0, stdout: str = "", stderr: str = "") -> Any:
    r = MagicMock()
    r.returncode = exit_code
    r.stdout = stdout
    r.stderr = stderr
    return r


def _step(
    id: str,
    seq: int,
    command: str,
    policy: str = "escalate",
    max_retries: int = 1,
    timeout: int = 30,
    desc: str = "",
) -> WorkflowStep:
    return WorkflowStep(
        id=id,
        seq=seq,
        command=command,
        description=desc or command,
        remediation_policy=policy,
        max_retries=max_retries,
        timeout_seconds=timeout,
    )


# ─── Agent trace dataclass ────────────────────────────────────────────────────


@dataclass
class AgentTrace:
    """One dispatch+return cycle through the supervisor hub."""
    round: int
    agent: str
    summary: str


# ─── MockSupervisor ───────────────────────────────────────────────────────────


@dataclass
class MockSupervisor:
    """Scripted Supervisor — returns pre-built workflows, records all calls.

    remediate_workflows is a per-round list: index 0 = round 1, index 1 = round 2, etc.
    If a round exceeds the list length an empty workflow is returned (step skipped).
    For convenience, pass a single remediate_workflow to use the same one every round.
    """

    plan_agents: List[AgentTrace]
    plan_workflow: Workflow

    remediate_agents: List[AgentTrace] = field(default_factory=list)
    remediate_workflow: Optional[Workflow] = None
    remediate_workflows: List[Optional[Workflow]] = field(default_factory=list)

    # state recorded during run
    remediate_calls: int = field(default=0, init=False)
    remediate_contexts: List[SupervisorContext] = field(default_factory=list, init=False)
    _plan_session: str = field(default="", init=False)

    def plan(self, request: str, draft: str = "") -> Tuple[SupervisorContext, Workflow]:
        ctx = SupervisorContext(
            mode=PipelineMode.PLANNING,
            original_request=request,
            draft=draft or request,
        )
        self._plan_session = ctx.session_id
        return ctx, self.plan_workflow

    def remediate(self, ctx: SupervisorContext) -> Tuple[SupervisorContext, Workflow]:
        idx = self.remediate_calls
        self.remediate_calls += 1
        self.remediate_contexts.append(ctx)
        ctx.mode = PipelineMode.REMEDIATING
        ctx.remediation_round += 1
        # per-round list takes precedence over single workflow
        if self.remediate_workflows:
            wf = (
                self.remediate_workflows[idx]
                if idx < len(self.remediate_workflows)
                else None
            )
        else:
            wf = self.remediate_workflow
        return ctx, wf or Workflow(session_id=ctx.session_id, steps=[])


# ─── Rendering ────────────────────────────────────────────────────────────────


def p(s: str = "") -> None:
    print(s)


def hdr(n: int, title: str, subtitle: str) -> None:
    inner = W - 2
    p(f"╔{'═' * inner}╗")
    p(f"║  SCENARIO {n} · {title:<{inner - 14}}║")
    p(f"║  {subtitle:<{inner - 2}}║")
    p(f"╚{'═' * inner}╝")


def sec(title: str) -> None:
    pad = max(1, W - 6 - len(title))
    p(f"\n  ── {title} {'─' * pad}")
    p()


def _planning_trace(agents: List[AgentTrace]) -> None:
    for ag in agents:
        p(f"    [{ag.round}] Supervisor  ──▶  {ag.agent}")
        for line in textwrap.wrap(ag.summary, 60):
            p(f"               ◀──  {line}")
        p()


def _workflow_table(steps: List[WorkflowStep]) -> None:
    cols = [4, 44, 20, 6]
    sep_top = "    ┌" + "┬".join("─" * (c + 2) for c in cols) + "┐"
    sep_mid = "    ├" + "┼".join("─" * (c + 2) for c in cols) + "┤"
    sep_bot = "    └" + "┴".join("─" * (c + 2) for c in cols) + "┘"

    def row(cells: List[str]) -> str:
        return "    │" + "│".join(f" {c:<{cols[i]}} " for i, c in enumerate(cells)) + "│"

    p(sep_top)
    p(row(["seq", "command", "policy", "t/o"]))
    p(sep_mid)
    for s in steps:
        cmd_d = s.command if len(s.command) <= cols[1] else s.command[:cols[1] - 1] + "…"
        pol_d = (
            f"{s.remediation_policy}(×{s.max_retries})"
            if s.max_retries > 1
            else s.remediation_policy
        )
        p(row([str(s.seq), cmd_d, pol_d, f"{s.timeout_seconds}s"]))
    p(sep_bot)


def _exec_trace(evidence: List[Evidence], final_wf: Workflow) -> None:
    """Render step-by-step execution evidence as a tree."""
    # Group evidence by step_id, preserving encounter order
    order: List[str] = []
    groups: Dict[str, List[Evidence]] = {}
    for ev in evidence:
        if ev.step_id not in groups:
            order.append(ev.step_id)
            groups[ev.step_id] = []
        groups[ev.step_id].append(ev)

    step_map = {s.id: s for s in final_wf.steps}

    for idx, step_id in enumerate(order):
        evs = groups[step_id]
        is_last = idx == len(order) - 1
        branch = "└─" if is_last else "├─"
        pipe = "   " if is_last else "│  "
        step = step_map.get(step_id)
        pol = step.remediation_policy if step else "?"
        cmd = evs[0].command
        cmd_d = cmd if len(cmd) <= 44 else cmd[:43] + "…"
        p(f"    {branch} [{step_id}]  {cmd_d}")
        p(f"    {pipe}     policy={pol}")

        for j, ev in enumerate(evs):
            ev_last = j == len(evs) - 1
            ev_conn = "└─" if ev_last else "├─"
            status = "exit=0 ✓" if ev.succeeded else f"exit={ev.exit_code} ✗"
            p(f"    {pipe}  {ev_conn} attempt {ev.attempt}  {status}")
            if ev.stderr and not ev.succeeded:
                clipped = ev.stderr.replace("\n", " ")[:62]
                p(f"    {pipe}       stderr: \"{clipped}\"")

        outcome = evs[-1]
        action_label = {
            "skip":    "↪  SKIPPED",
            "abort":   "⛔  WORKFLOW ABORTED",
            "retry":   "↺  RETRIED",
            "escalate": "⟲  ESCALATED TO SUPERVISOR",
        }
        if outcome.succeeded:
            p(f"    {pipe}  → ✓  PASSED")
        else:
            label = action_label.get(pol, "✗  FAILED")
            p(f"    {pipe}  → {label}")

        if not is_last:
            p(f"    │")


def _remediation_section(
    supervisor: MockSupervisor,
    original_wf: Workflow,
    final_wf: Workflow,
) -> None:
    iw = W - 8

    for i, rem_ctx in enumerate(supervisor.remediate_contexts, 1):
        failed = rem_ctx.failed_step_ids
        draft_preview = (rem_ctx.draft or "")[:180]

        # Determine what this specific round produced
        if supervisor.remediate_workflows:
            round_wf = (
                supervisor.remediate_workflows[i - 1]
                if i - 1 < len(supervisor.remediate_workflows)
                else None
            )
        else:
            round_wf = supervisor.remediate_workflow
        round_patch_ids = [s.id for s in (round_wf.steps if round_wf else [])]

        p(f"  ┌── REMEDIATION ROUND {i} {'─' * (iw - 22 - len(str(i)))}┐")

        # failed step + draft
        p(f"  │  failed steps : {', '.join(failed)}")
        for line in draft_preview.split("\n"):
            clipped = line[:iw - 4]
            if clipped:
                p(f"  │  {clipped}")

        p(f"  │  {'─' * (iw - 2)}")

        if round_patch_ids:
            # agent dispatches (hub-and-spoke, 3 agents)
            for ag in supervisor.remediate_agents:
                p(f"  │  [{ag.round}] Supervisor  ──▶  {ag.agent}")
                for line in textwrap.wrap(ag.summary, 56):
                    p(f"  │               ◀──  {line}")
            p(f"  │  {'─' * (iw - 2)}")
            p(f"  │  PATCH APPLIED  {'  '.join(f'{fid} ──▶ {pid}' for fid, pid in zip(failed, round_patch_ids))}")
        else:
            p(f"  │  Supervisor ran pipeline — no replacement commands found")
            p(f"  │  {'─' * (iw - 2)}")
            p(f"  │  ⚠  No patch produced — step will be skipped by harness")

        p(f"  └─{'─' * iw}─┘")
        p()


def _summary(evidence: List[Evidence], supervisor: MockSupervisor) -> None:
    step_ids = list({ev.step_id: None for ev in evidence})  # ordered unique
    passed = sum(1 for sid in step_ids if any(e.succeeded for e in evidence if e.step_id == sid))
    total = len(step_ids)
    retries = sum(1 for ev in evidence if ev.attempt > 1)
    rems = supervisor.remediate_calls

    icons = []
    if passed == total:
        icons.append("✓  all steps passed")
    else:
        icons.append(f"⚠  {total - passed} step(s) did not pass")
    if retries:
        icons.append(f"{retries} retry attempt(s)")
    if rems:
        icons.append(f"{rems} remediation round(s)")
    else:
        icons.append("no remediation needed")

    p(f"\n  {'─' * (W - 2)}")
    p(f"  RESULT  {passed}/{total} steps passed   ·   {' · '.join(icons[1:])}")
    p(f"  {'─' * (W - 2)}\n")


# ─── Scenario runner ──────────────────────────────────────────────────────────


def run(
    n: int,
    title: str,
    description: str,
    request: str,
    supervisor: MockSupervisor,
    subprocess_results: List[Any],
) -> None:
    hdr(n, title, description)
    p(f"\n  REQUEST  \"{request}\"")

    sec("PLANNING PIPELINE  (hub-and-spoke: every agent returns before next fires)")
    _planning_trace(supervisor.plan_agents)

    ctx, workflow = supervisor.plan(request)
    original_wf = workflow

    sec("WORKFLOW")
    _workflow_table(workflow.steps)
    p()

    sec("EXECUTION")
    with patch("subprocess.run", side_effect=subprocess_results):
        harness = HarnessRunner(supervisor)
        evidence, final_wf = harness.run(ctx, workflow)

    _exec_trace(evidence, final_wf)

    if supervisor.remediate_calls > 0:
        sec(f"REMEDIATION  ({supervisor.remediate_calls} round(s))")
        _remediation_section(supervisor, original_wf, final_wf)

    _summary(evidence, supervisor)


# ─── Scenarios ────────────────────────────────────────────────────────────────


def scenario_1_happy_path() -> None:
    """All steps succeed. No retries, no remediation."""
    sup = MockSupervisor(
        plan_agents=[
            AgentTrace(1, "IntakeAgent",
                "cleaned draft · 2 commands: [install-curl, verify-curl]"),
            AgentTrace(2, "SecurityAgent",
                "findings=0 · blocked=[] · approved=[install-curl, verify-curl]"),
            AgentTrace(3, "ComplianceAgent",
                "order=[install-curl, verify-curl] · policies: {install-curl: retry×2, verify-curl: skip}"),
            AgentTrace(4, "WorkflowAgent",
                "2 steps structured and emitted"),
        ],
        plan_workflow=Workflow(
            session_id="demo-1",
            source_request="install curl and verify it works",
            steps=[
                _step("install-curl", 1, "apt-get install -y curl", "retry", 2, 120),
                _step("verify-curl",  2, "curl --version",          "skip",  1, 30),
            ],
        ),
    )
    run(
        1, "Happy Path",
        "All steps succeed — no retries, no remediation triggered",
        "Install curl and verify it works",
        sup,
        [_proc(0, "Reading package lists…\ncurl installed"), _proc(0, "curl 8.11.0")],
    )


def scenario_2_skip_policy() -> None:
    """Middle step fails with skip policy — execution continues to next step."""
    sup = MockSupervisor(
        plan_agents=[
            AgentTrace(1, "IntakeAgent",
                "3 commands: [update-pkg, install-jq, verify-jq]"),
            AgentTrace(2, "SecurityAgent",
                "findings=0 · all approved"),
            AgentTrace(3, "ComplianceAgent",
                "policies: {update-pkg: retry×3, install-jq: skip, verify-jq: skip}"),
            AgentTrace(4, "WorkflowAgent",
                "3 steps structured and emitted"),
        ],
        plan_workflow=Workflow(
            session_id="demo-2",
            steps=[
                _step("update-pkg",  1, "apt-get update -y",    "retry",   3, 120),
                _step("install-jq",  2, "apt-get install -y jq","skip",    1, 120),
                _step("verify-jq",   3, "jq --version",          "skip",   1, 30),
            ],
        ),
    )
    run(
        2, "Skip Policy",
        "Step 2 fails (policy=skip) — skipped, execution continues to step 3",
        "Update packages and install jq",
        sup,
        [
            _proc(0, "Hit http://archive.ubuntu.com"),
            _proc(1, "", "E: Unable to locate package jq"),
            _proc(0, "jq-1.7.1"),
        ],
    )


def scenario_3_abort_policy() -> None:
    """First step fails with abort policy — workflow stops immediately."""
    sup = MockSupervisor(
        plan_agents=[
            AgentTrace(1, "IntakeAgent",
                "2 commands: [mount-volume, write-config]"),
            AgentTrace(2, "SecurityAgent",
                "findings=1 (mount requires elevated perms, medium severity) · 0 blocked"),
            AgentTrace(3, "ComplianceAgent",
                "policies: {mount-volume: abort, write-config: escalate}"),
            AgentTrace(4, "WorkflowAgent",
                "2 steps structured and emitted"),
        ],
        plan_workflow=Workflow(
            session_id="demo-3",
            steps=[
                _step("mount-volume",  1, "mount /dev/sdb1 /mnt/data", "abort", 1, 30),
                _step("write-config",  2, "cp config.yml /mnt/data/",  "escalate", 1, 30),
            ],
        ),
    )
    run(
        3, "Abort Policy",
        "Step 1 fails (policy=abort) — workflow stops immediately, step 2 never runs",
        "Mount data volume and copy config",
        sup,
        [_proc(1, "", "mount: only root can do that")],
    )


def scenario_4_retry_success() -> None:
    """Step fails on attempt 1, succeeds on attempt 2 (max_retries=2)."""
    sup = MockSupervisor(
        plan_agents=[
            AgentTrace(1, "IntakeAgent",
                "2 commands: [pull-image, run-container]"),
            AgentTrace(2, "SecurityAgent",
                "findings=0 · all approved"),
            AgentTrace(3, "ComplianceAgent",
                "policies: {pull-image: retry×3, run-container: escalate}"),
            AgentTrace(4, "WorkflowAgent",
                "2 steps structured and emitted"),
        ],
        plan_workflow=Workflow(
            session_id="demo-4",
            steps=[
                _step("pull-image",    1, "docker pull nginx:latest", "retry", 3, 120),
                _step("run-container", 2, "docker run -d nginx",      "escalate", 1, 30),
            ],
        ),
    )
    run(
        4, "Retry → Success",
        "Step 1 fails on attempt 1 (network flap), succeeds on attempt 2",
        "Pull and start nginx container",
        sup,
        [
            _proc(1, "", "Error: connection reset by peer"),  # attempt 1 fails
            _proc(0, "nginx:latest: Pull complete"),           # attempt 2 succeeds
            _proc(0, "a1b2c3d4e5f6"),                          # step 2 succeeds
        ],
    )


def scenario_5_retry_exhausted_escalate() -> None:
    """Retries exhausted → supervisor remediates → patch step succeeds."""
    patch_wf = Workflow(
        session_id="demo-5",
        mode="remediating",
        steps=[_step("pull-image-fix", 1,
                     "docker pull nginx:stable --platform linux/amd64",
                     "escalate", 1, 120)],
    )
    sup = MockSupervisor(
        plan_agents=[
            AgentTrace(1, "IntakeAgent",
                "2 commands: [pull-image, run-container]"),
            AgentTrace(2, "SecurityAgent",
                "findings=0 · all approved"),
            AgentTrace(3, "ComplianceAgent",
                "policies: {pull-image: retry×2, run-container: escalate}"),
            AgentTrace(4, "WorkflowAgent",
                "2 steps structured and emitted"),
        ],
        plan_workflow=Workflow(
            session_id="demo-5",
            steps=[
                _step("pull-image",    1, "docker pull nginx:latest", "retry", 2, 120),
                _step("run-container", 2, "docker run -d nginx",      "escalate", 1, 30),
            ],
        ),
        remediate_agents=[
            AgentTrace(1, "IntakeAgent",
                "1 remediation command: [pull-image-fix] add --platform flag"),
            AgentTrace(2, "SecurityAgent",
                "findings=0 · patch command approved"),
            AgentTrace(3, "WorkflowAgent",
                "1 patch step emitted at seq=1"),
        ],
        remediate_workflow=patch_wf,
    )
    run(
        5, "Retry Exhausted → Escalate → Patch",
        "Step 1 exhausts retries (policy=retry×2) → escalated → supervisor patches → succeeds",
        "Pull and start nginx container",
        sup,
        [
            _proc(1, "", "Error: manifest unknown"),  # attempt 1
            _proc(1, "", "Error: manifest unknown"),  # attempt 2 — retries exhausted
            _proc(0, "nginx:stable: Pull complete"),   # patch step succeeds
            _proc(0, "a1b2c3d4e5f6"),                  # run-container
        ],
    )


def scenario_6_direct_escalate() -> None:
    """Step fails directly (policy=escalate) → supervisor remediates → patch succeeds."""
    patch_wf = Workflow(
        session_id="demo-6",
        mode="remediating",
        steps=[_step("fix-service", 2,
                     "systemctl restart nginx --force",
                     "escalate", 1, 30)],
    )
    sup = MockSupervisor(
        plan_agents=[
            AgentTrace(1, "IntakeAgent",
                "2 commands: [start-service, check-status]"),
            AgentTrace(2, "SecurityAgent",
                "findings=1 (systemctl medium) · 0 blocked"),
            AgentTrace(3, "ComplianceAgent",
                "policies: {start-service: escalate, check-status: skip}"),
            AgentTrace(4, "WorkflowAgent",
                "2 steps structured and emitted"),
        ],
        plan_workflow=Workflow(
            session_id="demo-6",
            steps=[
                _step("start-service", 1, "systemctl start nginx",  "escalate", 1, 30),
                _step("check-status",  2, "systemctl status nginx", "skip",     1, 30),
            ],
        ),
        remediate_agents=[
            AgentTrace(1, "IntakeAgent",
                "1 command: [fix-service] add --force flag"),
            AgentTrace(2, "SecurityAgent",
                "findings=0 · approved"),
            AgentTrace(3, "WorkflowAgent",
                "1 patch step emitted at seq=1"),
        ],
        remediate_workflow=patch_wf,
    )
    run(
        6, "Direct Escalate → Patch Succeeds",
        "Step 1 fails (policy=escalate) → supervisor produces patch → patch step succeeds",
        "Start nginx and check its status",
        sup,
        [
            _proc(1, "", "Failed to start nginx.service: Unit not found"),  # original fails
            _proc(0, ""),   # fix-service patch succeeds
            _proc(0, "● nginx.service - A high performance web server"),  # check-status
        ],
    )


def scenario_7_max_remediation_rounds() -> None:
    """Round 1 patch also fails; round 2 escalation hits max_rounds (2) → step skipped."""
    # Round 1 → supervisor returns fix-disk patch
    # Round 2 → fix-disk also fails; supervisor returns empty workflow → step skipped
    round1_wf = Workflow(
        session_id="demo-7",
        mode="remediating",
        steps=[_step("fix-disk", 1, "fsck -y /dev/sda1", "escalate", 1, 60)],
    )
    # Round 2 returns nothing — harness skips the step and moves on
    round2_wf = Workflow(session_id="demo-7", mode="remediating", steps=[])

    sup = MockSupervisor(
        plan_agents=[
            AgentTrace(1, "IntakeAgent",
                "2 commands: [check-disk, mount-disk]"),
            AgentTrace(2, "SecurityAgent",
                "findings=1 (fsck on mounted fs, high severity) · 0 blocked"),
            AgentTrace(3, "ComplianceAgent",
                "policies: {check-disk: escalate, mount-disk: skip}"),
            AgentTrace(4, "WorkflowAgent",
                "2 steps structured and emitted"),
        ],
        plan_workflow=Workflow(
            session_id="demo-7",
            steps=[
                _step("check-disk", 1, "fsck /dev/sda1",    "escalate", 1, 60),
                _step("mount-disk", 2, "mount /dev/sda1 /", "skip",     1, 30),
            ],
        ),
        remediate_agents=[
            AgentTrace(1, "IntakeAgent",
                "1 remediation command: [fix-disk] add -y flag for auto-repair"),
            AgentTrace(2, "SecurityAgent",
                "findings=0 · approved"),
            AgentTrace(3, "WorkflowAgent",
                "1 patch step at seq=1"),
        ],
        remediate_workflows=[round1_wf, round2_wf],
    )
    run(
        7, "Max Remediation Rounds",
        "Round-1 patch fails again; round-2 returns empty → harness skips, continues",
        "Run disk check and mount volume",
        sup,
        [
            _proc(1, "", "fsck: error 8: superblock invalid"),  # check-disk fails
            _proc(1, "", "fsck: error 8: device busy"),          # fix-disk (round-1 patch) fails
            # round-2 returns empty → fix-disk skipped, step_index moves to mount-disk
            _proc(0, ""),                                         # mount-disk succeeds
        ],
    )


def scenario_8_security_blocking() -> None:
    """SecurityAgent blocks one command; workflow has one fewer step than intake extracted."""
    sup = MockSupervisor(
        plan_agents=[
            AgentTrace(1, "IntakeAgent",
                "3 commands: [update-pkg, rm-world-write, install-fail2ban]"),
            AgentTrace(2, "SecurityAgent",
                "findings=2 · blocked=[rm-world-write] (critical: recursive rm with "
                "broad glob) · approved=[update-pkg, install-fail2ban]"),
            AgentTrace(3, "ComplianceAgent",
                "order=[update-pkg, install-fail2ban] · "
                "policies: {update-pkg: retry×2, install-fail2ban: escalate}"),
            AgentTrace(4, "WorkflowAgent",
                "2 steps emitted (rm-world-write was blocked — omitted from workflow)"),
        ],
        plan_workflow=Workflow(
            session_id="demo-8",
            steps=[
                _step("update-pkg",      1, "apt-get update -y",                 "retry",   2, 120),
                _step("install-fail2ban",2, "apt-get install -y fail2ban",       "escalate",1, 120),
            ],
        ),
    )
    run(
        8, "Security Blocking",
        "SecurityAgent blocks 'rm -rf /tmp/*' (critical); workflow has 2 not 3 steps",
        "Update packages, remove world-writable files, install fail2ban",
        sup,
        [
            _proc(0, "Hit http://archive.ubuntu.com"),
            _proc(0, "fail2ban 1.0.2 installed"),
        ],
    )


def scenario_9_timeout_escalate() -> None:
    """Command times out (exit 124) → escalated → supervisor provides async alternative."""
    patch_wf = Workflow(
        session_id="demo-9",
        mode="remediating",
        steps=[_step("build-async", 2,
                     "nohup make -j4 > build.log 2>&1 &",
                     "skip", 1, 10)],
    )
    sup = MockSupervisor(
        plan_agents=[
            AgentTrace(1, "IntakeAgent",
                "2 commands: [configure, build]"),
            AgentTrace(2, "SecurityAgent",
                "findings=0 · all approved"),
            AgentTrace(3, "ComplianceAgent",
                "policies: {configure: retry×2, build: escalate}"),
            AgentTrace(4, "WorkflowAgent",
                "2 steps structured and emitted · build timeout=300s"),
        ],
        plan_workflow=Workflow(
            session_id="demo-9",
            steps=[
                _step("configure", 1, "./configure --prefix=/usr/local", "retry",   2, 60),
                _step("build",     2, "make -j4",                        "escalate",1, 300),
            ],
        ),
        remediate_agents=[
            AgentTrace(1, "IntakeAgent",
                "1 command: [build-async] run make in background with nohup"),
            AgentTrace(2, "SecurityAgent",
                "findings=0 · approved"),
            AgentTrace(3, "WorkflowAgent",
                "1 patch step emitted at seq=2 with timeout=10s"),
        ],
        remediate_workflow=patch_wf,
    )

    # Simulate timeout by raising subprocess.TimeoutExpired for the build step
    configure_ok = _proc(0, "configure: creating ./config.status")
    build_timeout = subprocess.TimeoutExpired("make -j4", 300)
    patch_ok = _proc(0, "")

    run(
        9, "Timeout (exit 124) → Escalate → Async Patch",
        "Build step times out (exit=124, policy=escalate) → supervisor provides background variant",
        "Configure and build from source",
        sup,
        [configure_ok, build_timeout, patch_ok],
    )


# ─── Main ─────────────────────────────────────────────────────────────────────

_ALL: List[Tuple[int, Any]] = [
    (1, scenario_1_happy_path),
    (2, scenario_2_skip_policy),
    (3, scenario_3_abort_policy),
    (4, scenario_4_retry_success),
    (5, scenario_5_retry_exhausted_escalate),
    (6, scenario_6_direct_escalate),
    (7, scenario_7_max_remediation_rounds),
    (8, scenario_8_security_blocking),
    (9, scenario_9_timeout_escalate),
]

_LEGEND = """\
  Legend
  ──────
  ──▶  supervisor dispatches to agent
  ◀──  agent returns to supervisor (hub-and-spoke: always via supervisor)
  ✓    step passed          ✗    step failed
  ↪    skipped (policy=skip)
  ⛔   workflow aborted (policy=abort)
  ↺    retried (policy=retry)
  ⟲    escalated to supervisor for remediation (policy=escalate)
"""


def main() -> None:
    nums = set(int(a) for a in sys.argv[1:] if a.isdigit())
    selected = [(n, fn) for n, fn in _ALL if not nums or n in nums]

    p()
    p("╔" + "═" * (W - 2) + "╗")
    p("║" + f"  SUPERVISOR HARNESS — SCENARIO DEMONSTRATIONS{'':<{W - 48}}" + "║")
    p("║" + f"  Sequential hub-and-spoke pipeline with evidence-driven remediation{'':<{W - 68}}" + "║")
    p("╚" + "═" * (W - 2) + "╝")
    p()
    p(_LEGEND)

    for i, (n, fn) in enumerate(selected):
        fn()
        if i < len(selected) - 1:
            p()
            p("  " + "─" * (W - 2))
            p()


if __name__ == "__main__":
    main()
