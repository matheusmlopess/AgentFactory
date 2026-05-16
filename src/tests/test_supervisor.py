"""Tests for the supervisor-harness pipeline.

All Claude API calls and subprocess executions are mocked so tests run
without network access or real shell commands.
"""
from __future__ import annotations

import subprocess
from typing import Any, Dict, List
from unittest.mock import MagicMock, call, patch

import pytest

from agent_gen.supervisor.context import (
    CommandStep,
    Evidence,
    PipelineMode,
    SupervisorContext,
)
from agent_gen.supervisor.harness import HarnessRunner, _failure_draft
from agent_gen.supervisor.workflow import Workflow, WorkflowStep


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_step(
    id: str = "step-1",
    seq: int = 1,
    command: str = "echo hello",
    policy: str = "escalate",
    max_retries: int = 1,
    timeout: int = 30,
) -> WorkflowStep:
    return WorkflowStep(
        id=id,
        seq=seq,
        command=command,
        remediation_policy=policy,
        max_retries=max_retries,
        timeout_seconds=timeout,
    )


def _make_workflow(steps: List[WorkflowStep] | None = None) -> Workflow:
    return Workflow(
        session_id="test-session",
        steps=steps or [_make_step()],
    )


# ---------------------------------------------------------------------------
# SupervisorContext
# ---------------------------------------------------------------------------


class TestSupervisorContext:
    def test_defaults(self):
        ctx = SupervisorContext()
        assert ctx.round == 0
        assert ctx.mode == PipelineMode.PLANNING
        assert ctx.commands == []
        assert ctx.evidence == []
        assert ctx.remediation_round == 0
        assert ctx.session_id  # non-empty uuid

    def test_to_brief_empty(self):
        ctx = SupervisorContext(original_request="test req")
        brief = ctx.to_brief()
        assert "test req" in brief
        assert "planning" in brief

    def test_to_brief_with_evidence(self):
        ctx = SupervisorContext()
        ctx.evidence.append(
            Evidence(step_id="s1", command="ls", exit_code=1, stdout="", stderr="err")
        )
        ctx.failed_step_ids = ["s1"]
        brief = ctx.to_brief()
        assert "1 failed" in brief
        assert "s1" in brief

    def test_evidence_succeeded(self):
        ev_ok = Evidence(step_id="s", command="x", exit_code=0, stdout="", stderr="")
        ev_fail = Evidence(step_id="s", command="x", exit_code=1, stdout="", stderr="")
        assert ev_ok.succeeded is True
        assert ev_fail.succeeded is False


# ---------------------------------------------------------------------------
# Workflow + patch
# ---------------------------------------------------------------------------


class TestWorkflow:
    def test_patch_replaces_failed_step(self):
        s1 = _make_step("s1", seq=1)
        s2 = _make_step("s2", seq=2)
        s3 = _make_step("s3", seq=3)
        workflow = _make_workflow([s1, s2, s3])

        replacement = _make_step("s2-fix", seq=2, command="apt-get install -y curl")
        patched = workflow.patch([replacement], ["s2"])

        ids = [s.id for s in patched.steps]
        assert "s2" not in ids
        assert "s2-fix" in ids
        assert "s1" in ids
        assert "s3" in ids
        assert patched.mode == "remediating"

    def test_patch_preserves_order_by_seq(self):
        s1 = _make_step("s1", seq=1)
        s3 = _make_step("s3", seq=3)
        workflow = _make_workflow([s1, _make_step("s2", seq=2), s3])

        replacement = _make_step("s2-fix", seq=2)
        patched = workflow.patch([replacement], ["s2"])
        seqs = [s.seq for s in patched.steps]
        assert seqs == sorted(seqs)

    def test_patch_empty_replacement_removes_failed_step(self):
        s1 = _make_step("s1", seq=1)
        s2 = _make_step("s2", seq=2)
        workflow = _make_workflow([s1, s2])
        patched = workflow.patch([], ["s2"])
        assert len(patched.steps) == 1
        assert patched.steps[0].id == "s1"


# ---------------------------------------------------------------------------
# HarnessRunner — subprocess mocking
# ---------------------------------------------------------------------------


def _mock_completed(returncode: int = 0, stdout: str = "", stderr: str = ""):
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


class TestHarnessRunnerDryRun:
    def test_dry_run_all_succeed(self):
        sup = MagicMock()
        runner = HarnessRunner(sup, dry_run=True)
        steps = [_make_step("s1"), _make_step("s2", seq=2)]
        wf = _make_workflow(steps)
        ctx = SupervisorContext()
        evidence, final_wf = runner.run(ctx, wf)
        assert len(evidence) == 2
        assert all(e.succeeded for e in evidence)
        assert final_wf is wf  # no patching needed

    def test_dry_run_populates_context_evidence(self):
        sup = MagicMock()
        runner = HarnessRunner(sup, dry_run=True)
        ctx = SupervisorContext()
        runner.run(ctx, _make_workflow())
        assert len(ctx.evidence) == 1


class TestHarnessRunnerLive:
    def test_success_path(self):
        with patch("subprocess.run", return_value=_mock_completed(0, "ok")) as mock_run:
            sup = MagicMock()
            runner = HarnessRunner(sup)
            ctx = SupervisorContext()
            evidence, _ = runner.run(ctx, _make_workflow([_make_step()]))
        assert evidence[0].succeeded
        mock_run.assert_called_once()

    def test_skip_policy_continues(self):
        results = [_mock_completed(1), _mock_completed(0)]
        with patch("subprocess.run", side_effect=results):
            sup = MagicMock()
            runner = HarnessRunner(sup)
            ctx = SupervisorContext()
            step1 = _make_step("s1", seq=1, policy="skip")
            step2 = _make_step("s2", seq=2)
            evidence, _ = runner.run(ctx, _make_workflow([step1, step2]))
        assert evidence[0].exit_code == 1
        assert evidence[1].succeeded

    def test_abort_policy_stops_execution(self):
        with patch("subprocess.run", return_value=_mock_completed(1)):
            sup = MagicMock()
            runner = HarnessRunner(sup)
            ctx = SupervisorContext()
            step1 = _make_step("s1", seq=1, policy="abort")
            step2 = _make_step("s2", seq=2)
            evidence, _ = runner.run(ctx, _make_workflow([step1, step2]))
        assert len(evidence) == 1  # stopped after s1

    def test_retry_policy_retries_then_succeeds(self):
        results = [_mock_completed(1), _mock_completed(0)]
        with patch("subprocess.run", side_effect=results):
            sup = MagicMock()
            runner = HarnessRunner(sup)
            ctx = SupervisorContext()
            step = _make_step("s1", policy="retry", max_retries=2)
            evidence, _ = runner.run(ctx, _make_workflow([step]))
        assert evidence[-1].succeeded
        assert len(evidence) == 2

    def test_retry_exhausted_escalates(self):
        patch_wf = MagicMock()
        patch_wf.steps = [_make_step("s1-fix", seq=1, command="fixed")]

        def _remediate(ctx):
            ctx.remediation_round += 1
            return ctx, patch_wf

        sup = MagicMock()
        sup.remediate.side_effect = _remediate

        with patch("subprocess.run", side_effect=[
            _mock_completed(1),   # attempt 1
            _mock_completed(1),   # attempt 2 (max_retries=2)
            _mock_completed(0),   # remediated step succeeds
        ]):
            runner = HarnessRunner(sup)
            ctx = SupervisorContext()
            step = _make_step("s1", policy="retry", max_retries=2)
            evidence, final_wf = runner.run(ctx, _make_workflow([step]))

        sup.remediate.assert_called_once()
        assert evidence[-1].succeeded

    def test_escalate_calls_supervisor_remediate(self):
        patch_wf = MagicMock()
        patch_wf.steps = [_make_step("s1-fix", seq=1, command="fixed")]

        def _remediate(ctx):
            ctx.remediation_round += 1
            return ctx, patch_wf

        sup = MagicMock()
        sup.remediate.side_effect = _remediate

        with patch("subprocess.run", side_effect=[
            _mock_completed(1),  # original fails
            _mock_completed(0),  # remediated step succeeds
        ]):
            runner = HarnessRunner(sup)
            ctx = SupervisorContext()
            step = _make_step("s1", policy="escalate")
            evidence, final_wf = runner.run(ctx, _make_workflow([step]))

        sup.remediate.assert_called_once()
        assert evidence[-1].succeeded

    def test_max_remediation_rounds_skips_after_limit(self):
        with patch("subprocess.run", return_value=_mock_completed(1)):
            sup = MagicMock()
            runner = HarnessRunner(sup)
            ctx = SupervisorContext()
            ctx.remediation_round = 2  # already at max
            step = _make_step("s1", policy="escalate")
            evidence, _ = runner.run(ctx, _make_workflow([step]))
        sup.remediate.assert_not_called()

    def test_timeout_produces_exit_124(self):
        with patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 5)
        ):
            sup = MagicMock()
            runner = HarnessRunner(sup)
            ctx = SupervisorContext()
            step = _make_step("s1", policy="skip", timeout=5)
            evidence, _ = runner.run(ctx, _make_workflow([step]))
        assert evidence[0].exit_code == 124
        assert "timed out" in evidence[0].stderr


# ---------------------------------------------------------------------------
# _failure_draft helper
# ---------------------------------------------------------------------------


class TestFailureDraft:
    def test_includes_command(self):
        step = _make_step(command="rm -rf /tmp/x")
        draft = _failure_draft(step, [])
        assert "rm -rf /tmp/x" in draft

    def test_includes_stderr_from_evidence(self):
        step = _make_step("s1")
        ev = Evidence(step_id="s1", command="x", exit_code=1, stdout="", stderr="file not found")
        draft = _failure_draft(step, [ev])
        assert "file not found" in draft

    def test_uses_most_recent_evidence(self):
        step = _make_step("s1")
        ev1 = Evidence(step_id="s1", command="x", exit_code=1, stdout="", stderr="first error")
        ev2 = Evidence(step_id="s1", command="x", exit_code=1, stdout="", stderr="second error")
        draft = _failure_draft(step, [ev1, ev2])
        assert "second error" in draft
        assert "first error" not in draft


# ---------------------------------------------------------------------------
# End-to-end scenario tests  (all subprocess + supervisor calls are mocked)
#
# Each test maps 1-to-1 with a scenario in demo.py.  The assertions focus on
# observable outcomes: how many subprocess calls happened, whether
# supervisor.remediate was called, the final step count, and evidence shape.
# ---------------------------------------------------------------------------


def _scenario_workflow(*steps: WorkflowStep) -> Workflow:
    return Workflow(session_id="test", steps=list(steps))


def _scripted_supervisor(
    plan_wf: Workflow,
    remediate_wfs: List[Workflow] | None = None,
) -> MagicMock:
    """Build a MagicMock supervisor whose plan() / remediate() return scripted workflows."""
    sup = MagicMock()
    ctx = SupervisorContext(mode="planning", original_request="test")
    sup.plan.return_value = (ctx, plan_wf)

    rem_wfs = list(remediate_wfs or [])
    call_count = {"n": 0}

    def _remediate(c):
        idx = call_count["n"]
        call_count["n"] += 1
        c.remediation_round += 1
        wf = rem_wfs[idx] if idx < len(rem_wfs) else Workflow(session_id=c.session_id, steps=[])
        return c, wf

    sup.remediate.side_effect = _remediate
    return sup


class TestScenarios:
    """Full pipeline scenario tests mirroring demo.py scenarios 1-9."""

    # ── Scenario 1: Happy Path ──────────────────────────────────────────────

    def test_s1_happy_path_all_steps_succeed(self):
        """2 steps, both exit=0. No retries, no remediation."""
        wf = _scenario_workflow(
            _make_step("s1", seq=1, policy="retry", max_retries=2),
            _make_step("s2", seq=2, policy="skip"),
        )
        sup = _scripted_supervisor(wf)
        with patch("subprocess.run", side_effect=[
            _mock_completed(0, "installed"), _mock_completed(0, "8.11.0")
        ]):
            runner = HarnessRunner(sup)
            ctx = SupervisorContext()
            evidence, final_wf = runner.run(ctx, wf)

        assert all(e.succeeded for e in evidence)
        assert len(evidence) == 2
        sup.remediate.assert_not_called()

    # ── Scenario 2: Skip Policy ─────────────────────────────────────────────

    def test_s2_skip_continues_to_next_step(self):
        """Step 2 fails (skip) → step 3 still runs."""
        wf = _scenario_workflow(
            _make_step("s1", seq=1, policy="retry",   max_retries=3),
            _make_step("s2", seq=2, policy="skip"),
            _make_step("s3", seq=3, policy="skip"),
        )
        sup = _scripted_supervisor(wf)
        with patch("subprocess.run", side_effect=[
            _mock_completed(0),   # s1 ok
            _mock_completed(1, stderr="not found"),  # s2 fails — skipped
            _mock_completed(0),   # s3 ok
        ]):
            evidence, final_wf = HarnessRunner(sup).run(SupervisorContext(), wf)

        assert len(evidence) == 3
        assert evidence[0].succeeded
        assert not evidence[1].succeeded
        assert evidence[2].succeeded
        sup.remediate.assert_not_called()

    # ── Scenario 3: Abort Policy ────────────────────────────────────────────

    def test_s3_abort_stops_workflow_immediately(self):
        """Step 1 fails (abort) → step 2 never runs."""
        wf = _scenario_workflow(
            _make_step("s1", seq=1, policy="abort"),
            _make_step("s2", seq=2, policy="escalate"),
        )
        sup = _scripted_supervisor(wf)
        with patch("subprocess.run", return_value=_mock_completed(1, stderr="permission denied")):
            evidence, final_wf = HarnessRunner(sup).run(SupervisorContext(), wf)

        assert len(evidence) == 1   # s2 never ran
        assert not evidence[0].succeeded
        sup.remediate.assert_not_called()

    # ── Scenario 4: Retry → Success ─────────────────────────────────────────

    def test_s4_retry_succeeds_on_second_attempt(self):
        """Step fails once, retries (max_retries=2) and succeeds on attempt 2."""
        wf = _scenario_workflow(
            _make_step("s1", seq=1, policy="retry", max_retries=2),
            _make_step("s2", seq=2),
        )
        sup = _scripted_supervisor(wf)
        with patch("subprocess.run", side_effect=[
            _mock_completed(1, stderr="network error"),  # attempt 1
            _mock_completed(0, "Pull complete"),          # attempt 2
            _mock_completed(0),                            # s2
        ]):
            evidence, _ = HarnessRunner(sup).run(SupervisorContext(), wf)

        assert len(evidence) == 3
        assert evidence[1].attempt == 2
        assert evidence[1].succeeded
        sup.remediate.assert_not_called()

    # ── Scenario 5: Retry Exhausted → Escalate → Patch ──────────────────────

    def test_s5_retry_exhausted_triggers_escalation_and_patch_succeeds(self):
        """max_retries exhausted → supervisor.remediate → patch step succeeds."""
        patch_wf = _scenario_workflow(
            _make_step("s1-fix", seq=1, command="docker pull nginx:stable")
        )
        wf = _scenario_workflow(
            _make_step("s1", seq=1, policy="retry", max_retries=2,
                       command="docker pull nginx:latest"),
            _make_step("s2", seq=2),
        )
        sup = _scripted_supervisor(wf, remediate_wfs=[patch_wf])
        with patch("subprocess.run", side_effect=[
            _mock_completed(1, stderr="manifest unknown"),  # attempt 1
            _mock_completed(1, stderr="manifest unknown"),  # attempt 2 — exhausted
            _mock_completed(0, "Pull complete"),              # s1-fix patch
            _mock_completed(0),                               # s2
        ]):
            evidence, final_wf = HarnessRunner(sup).run(SupervisorContext(), wf)

        sup.remediate.assert_called_once()
        patch_ids = [s.id for s in final_wf.steps]
        assert "s1-fix" in patch_ids
        assert "s1" not in patch_ids
        # last evidence entry for the patched step must succeed
        assert evidence[-2].step_id == "s1-fix"
        assert evidence[-2].succeeded

    # ── Scenario 6: Direct Escalate → Patch Succeeds ────────────────────────

    def test_s6_direct_escalate_remediates_and_patch_step_runs(self):
        """Single step fails (escalate) → supervisor remediates → patch runs and passes."""
        patch_wf = _scenario_workflow(
            _make_step("s1-fix", seq=1, command="systemctl restart nginx --force")
        )
        wf = _scenario_workflow(
            _make_step("s1", seq=1, policy="escalate", command="systemctl start nginx"),
            _make_step("s2", seq=2, policy="skip", command="systemctl status nginx"),
        )
        sup = _scripted_supervisor(wf, remediate_wfs=[patch_wf])
        with patch("subprocess.run", side_effect=[
            _mock_completed(1, stderr="Unit not found"),  # s1 fails
            _mock_completed(0),                             # s1-fix patch passes
            _mock_completed(0, "active (running)"),         # s2
        ]):
            evidence, final_wf = HarnessRunner(sup).run(SupervisorContext(), wf)

        sup.remediate.assert_called_once()
        assert any(e.step_id == "s1-fix" and e.succeeded for e in evidence)

    # ── Scenario 7: Max Remediation Rounds ──────────────────────────────────

    def test_s7_max_remediation_rounds_skips_unfixable_step(self):
        """Round 1 patch also fails; round 2 returns empty → step skipped, next runs."""
        round1_wf = _scenario_workflow(
            _make_step("s1-fix", seq=1, policy="escalate", command="fsck -y /dev/sda1")
        )
        round2_wf = Workflow(session_id="test", steps=[])  # nothing produced

        wf = _scenario_workflow(
            _make_step("s1", seq=1, policy="escalate", command="fsck /dev/sda1"),
            _make_step("s2", seq=2, policy="skip",     command="mount /dev/sda1 /"),
        )
        sup = _scripted_supervisor(wf, remediate_wfs=[round1_wf, round2_wf])
        with patch("subprocess.run", side_effect=[
            _mock_completed(1, stderr="superblock invalid"),  # s1 fails
            _mock_completed(1, stderr="device busy"),          # s1-fix also fails
            # round 2 returns empty → step skipped, s2 runs
            _mock_completed(0),                                # s2
        ]):
            evidence, _ = HarnessRunner(sup).run(SupervisorContext(), wf)

        assert sup.remediate.call_count == 2
        assert evidence[-1].step_id == "s2"
        assert evidence[-1].succeeded

    # ── Scenario 8: Security Blocking ───────────────────────────────────────

    def test_s8_security_blocked_command_absent_from_workflow(self):
        """When SecurityAgent blocks a command the workflow has fewer steps than extracted."""
        # This scenario is purely a planning concern — the workflow itself just has 2 steps
        wf = _scenario_workflow(
            _make_step("update-pkg",      seq=1, policy="retry", max_retries=2),
            _make_step("install-fail2ban",seq=2, policy="escalate"),
            # "rm-world-write" command was blocked and never appears here
        )
        sup = _scripted_supervisor(wf)
        with patch("subprocess.run", side_effect=[
            _mock_completed(0, "packages updated"),
            _mock_completed(0, "fail2ban installed"),
        ]):
            evidence, final_wf = HarnessRunner(sup).run(SupervisorContext(), wf)

        assert len(final_wf.steps) == 2
        step_ids = [s.id for s in final_wf.steps]
        assert "rm-world-write" not in step_ids
        assert all(e.succeeded for e in evidence)

    # ── Scenario 9: Timeout → Escalate → Async Patch ────────────────────────

    def test_s9_timeout_exits_124_escalates_to_supervisor(self):
        """Command times out (exit 124) → escalated → async background patch applied."""
        async_wf = _scenario_workflow(
            _make_step("build-async", seq=2, policy="skip",
                       command="nohup make -j4 > build.log 2>&1 &",
                       timeout=10)
        )
        wf = _scenario_workflow(
            _make_step("configure", seq=1, policy="retry", max_retries=2, timeout=60),
            _make_step("build",     seq=2, policy="escalate", timeout=300),
        )
        sup = _scripted_supervisor(wf, remediate_wfs=[async_wf])
        with patch("subprocess.run", side_effect=[
            _mock_completed(0, "config.status created"),       # configure ok
            subprocess.TimeoutExpired("make -j4", 300),         # build times out
            _mock_completed(0),                                  # build-async ok
        ]):
            evidence, final_wf = HarnessRunner(sup).run(SupervisorContext(), wf)

        timeout_ev = next(e for e in evidence if e.step_id == "build")
        assert timeout_ev.exit_code == 124
        assert "timed out" in timeout_ev.stderr

        sup.remediate.assert_called_once()
        patch_ids = [s.id for s in final_wf.steps]
        assert "build-async" in patch_ids
        assert evidence[-1].step_id == "build-async"
        assert evidence[-1].succeeded
