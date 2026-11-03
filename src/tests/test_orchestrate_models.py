"""Unit tests for orchestration models: steps, workflows, loading, templating."""
import json

import pytest

from agent_gen.orchestrate.models import (
    Evidence,
    RunResult,
    StepStatus,
    Workflow,
    WorkflowStep,
    load_workflow,
    validate_workflow_data,
)


class TestWorkflowStep:
    def test_from_dict_minimal_shell(self):
        step = WorkflowStep.from_dict({"id": "a", "command": "echo hi"})
        assert step.type == "shell"
        assert step.remediation == "escalate"

    def test_unknown_field_rejected(self):
        with pytest.raises(ValueError, match="unknown field"):
            WorkflowStep.from_dict({"id": "a", "command": "x", "bogus": 1})

    def test_branch_era_remediation_policy_alias(self):
        step = WorkflowStep.from_dict(
            {"id": "a", "command": "x", "remediation_policy": "retry"}
        )
        assert step.remediation == "retry"

    def test_unknown_type_rejected(self):
        with pytest.raises(ValueError, match="unknown type"):
            WorkflowStep.from_dict({"id": "a", "type": "warp", "command": "x"})

    def test_shell_requires_command(self):
        with pytest.raises(ValueError, match="requires 'command'"):
            WorkflowStep.from_dict({"id": "a", "type": "shell"})

    def test_agent_requires_prompt(self):
        with pytest.raises(ValueError, match="requires 'prompt'"):
            WorkflowStep.from_dict({"id": "a", "type": "agent"})

    def test_bad_expects_rejected(self):
        with pytest.raises(ValueError, match="expects"):
            WorkflowStep.from_dict(
                {"id": "a", "command": "x", "expects": "maybe"}
            )

    def test_regex_expects_accepted(self):
        step = WorkflowStep.from_dict(
            {"id": "a", "command": "x", "expects": "regex:^OK"}
        )
        assert step.expects == "regex:^OK"


class TestPromptTemplating:
    def _ev(self, step_id, stdout="out", exit_code=0):
        return Evidence(step_id=step_id, command="c", exit_code=exit_code,
                        stdout=stdout, stderr="err")

    def test_stdout_substitution(self):
        step = WorkflowStep(id="b", type="agent", prompt="Given: {steps.a.stdout}")
        rendered = step.render_prompt({"a": self._ev("a", stdout="hello")})
        assert rendered == "Given: hello"

    def test_exit_code_and_stderr(self):
        step = WorkflowStep(
            id="b", type="agent",
            prompt="{steps.a.exit_code} / {steps.a.stderr}",
        )
        assert step.render_prompt({"a": self._ev("a")}) == "0 / err"

    def test_unresolved_reference_left_visible(self):
        step = WorkflowStep(id="b", type="agent", prompt="{steps.ghost.stdout}")
        assert step.render_prompt({}) == "{steps.ghost.stdout}"

    def test_substitution_truncated(self):
        step = WorkflowStep(id="b", type="agent", prompt="{steps.a.stdout}")
        rendered = step.render_prompt({"a": self._ev("a", stdout="x" * 20_000)})
        assert len(rendered) == 8_000


class TestWorkflow:
    def _wf(self, steps):
        return {"name": "t", "steps": steps}

    def test_from_dict_assigns_seq(self):
        wf = Workflow.from_dict(self._wf([
            {"id": "a", "command": "x"}, {"id": "b", "command": "y"},
        ]))
        assert [s.seq for s in wf.steps] == [10, 20]

    def test_requires_name(self):
        with pytest.raises(ValueError, match="requires a 'name'"):
            Workflow.from_dict({"steps": []})

    def test_duplicate_ids_rejected(self):
        with pytest.raises(ValueError, match="duplicate step id"):
            Workflow.from_dict(self._wf([
                {"id": "a", "command": "x"}, {"id": "a", "command": "y"},
            ]))

    def test_unknown_depends_on_rejected(self):
        with pytest.raises(ValueError, match="depends_on unknown step"):
            Workflow.from_dict(self._wf([
                {"id": "a", "command": "x", "depends_on": ["ghost"]},
            ]))

    def test_patch_replaces_failed_step_in_seq_order(self):
        wf = Workflow.from_dict(self._wf([
            {"id": "a", "command": "x"},
            {"id": "bad", "command": "y"},
            {"id": "c", "command": "z"},
        ]))
        replacement = WorkflowStep(id="fixed", seq=20, command="y2")
        patched = wf.patch([replacement], ["bad"])
        assert [s.id for s in patched.steps] == ["a", "fixed", "c"]
        assert wf.steps[1].id == "bad"  # original untouched


class TestLoadWorkflow:
    def test_load_json(self, tmp_path):
        p = tmp_path / "t.workflow.json"
        p.write_text(json.dumps({"name": "t", "steps": [{"id": "a", "command": "x"}]}))
        wf = load_workflow(p)
        assert wf.name == "t" and len(wf.steps) == 1

    def test_load_md_wrapper_with_frontmatter(self, tmp_path):
        p = tmp_path / "t.md"
        p.write_text(
            "---\nname: from-md\nversion: 2.0.0\nmode: sequential\n---\n"
            "# Title\n<!-- version: 2.0.0 -->\n\nProse.\n\n"
            "```json\n{\"steps\": [{\"id\": \"a\", \"command\": \"x\"}]}\n```\n"
        )
        wf = load_workflow(p)
        assert wf.name == "from-md"
        assert wf.version == "2.0.0"
        assert wf.mode == "sequential"

    def test_load_md_without_json_block_fails(self, tmp_path):
        p = tmp_path / "t.md"
        p.write_text("---\nname: t\n---\nno block here\n")
        with pytest.raises(ValueError, match="json block"):
            load_workflow(p)

    def test_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_workflow(tmp_path / "ghost.workflow.json")

    def test_unsupported_extension(self, tmp_path):
        p = tmp_path / "t.yaml"
        p.write_text("name: t")
        with pytest.raises(ValueError, match="unsupported workflow format"):
            load_workflow(p)


class TestRunResult:
    def test_ok_requires_all_success_or_skipped(self):
        r = RunResult(workflow_name="t", workflow_id="w", mode="sequential")
        assert not r.ok  # empty = not ok
        r.statuses = {"a": StepStatus.SUCCESS.value, "b": StepStatus.SKIPPED.value}
        assert r.ok
        r.statuses["c"] = StepStatus.FAILED.value
        assert not r.ok

    def test_to_dict_round_trip(self):
        r = RunResult(workflow_name="t", workflow_id="w", mode="sequential")
        r.evidence.append(Evidence("a", "c", 0, "out", ""))
        data = json.loads(json.dumps(r.to_dict()))
        assert data["workflow_name"] == "t"
        assert data["evidence"][0]["step_id"] == "a"


def test_validate_workflow_data_reports_issue():
    assert validate_workflow_data({"steps": []}) == ["workflow requires a 'name'"]
    assert validate_workflow_data({"name": "t", "steps": []}) == []
    assert validate_workflow_data([1, 2]) == ["workflow root must be a JSON object"]
