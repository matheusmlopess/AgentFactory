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
