"""Orchestration contract — project-level configuration for orchestration runs.

The contract lives at .ai/config/orchestration.json (beside completeness.json)
and is OPTIONAL: built-in defaults cover the four registered CLI adapters plus
the nested-harness runner. When the file exists it deep-merges over defaults,
so users can override a single agent's invocation without restating the rest.

Per-agent `invocation` arrays are also the test seam: tests point an agent at
a stub script instead of monkeypatching subprocess.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from ..librarian import HARNESS_ROOT

CONTRACT_RELPATH = Path(HARNESS_ROOT) / "config" / "orchestration.json"

# Invocation templates: "{prompt}" is replaced with the rendered step prompt,
# "{workflow}" with a workflow path (nested harness runner).
# Proven flags — see src/tests/test_cli_swap_scenarios.py (_CLI_INVOCATION).
DEFAULT_CONTRACT: dict = {
    "version": "1.0.0",
    "default_mode": "sequential",
    "default_agent": "claude",
    "supervisor_agent": "claude",
    "agents": {
        "claude": {
            "invocation": ["claude", "--print", "{prompt}"],
        },
        "codex": {
            "invocation": ["codex", "exec", "--skip-git-repo-check", "{prompt}"],
            "stdin": "devnull",  # codex 0.142+ blocks on stdin otherwise
        },
        "gemini": {
            "invocation": ["gemini", "--prompt", "{prompt}"],
            "enabled": False,  # Gemini CLI retired 2026-06-18
        },
        "antigravity": {
            "invocation": ["agy", "-p", "{prompt}"],
        },
        "harness": {
            # Nested orchestration: a workflow step can run another workflow.
            "invocation": ["agentfactory-gen", "orchestrate", "run", "{workflow}", "--json"],
        },
    },
    "policies": {
        "default_remediation": "escalate",
        "max_retries": 1,
        "timeout_seconds": 300,
        "max_remediation_rounds": 2,
        "max_delegate_depth": 1,
        "max_parallel": 4,
        "allow_shell_steps": True,
        # An empty agent answer is never useful evidence (agy returns exit 0
        # with no output when quota is exhausted).
        "empty_output_is_failure": True,
    },
    "evidence": {
        "dir": f"{HARNESS_ROOT}/memory/orchestration-runs",
        "capture": {"stdout": True, "stderr": True, "exit_code": True},
    },
}


class OrchestrationContract:
    """Merged view of DEFAULT_CONTRACT and the project's orchestration.json."""

    def __init__(self, data: dict):
        self.data = data

    # -- accessors ---------------------------------------------------------

    @property
    def default_mode(self) -> str:
        return self.data.get("default_mode", "sequential")

    @property
    def default_agent(self) -> str:
        return self.data.get("default_agent", "claude")

    @property
    def supervisor_agent(self) -> str:
        return self.data.get("supervisor_agent", self.default_agent)

    @property
    def agents(self) -> dict:
        return self.data.get("agents", {})

    @property
    def policies(self) -> dict:
        return self.data.get("policies", {})

    @property
    def evidence_dir(self) -> str:
        return self.data.get("evidence", {}).get(
            "dir", DEFAULT_CONTRACT["evidence"]["dir"]
        )

    def agent_spec(self, name: str) -> dict:
        """Resolve an agent entry; raises for unknown or disabled agents."""
        spec = self.agents.get(name)
        if spec is None:
            raise ValueError(
                f"unknown agent '{name}' — declare it in {CONTRACT_RELPATH}"
            )
        if not spec.get("enabled", True):
            raise ValueError(f"agent '{name}' is disabled in the contract")
        return spec

    def validate(self) -> list[str]:
        """Return a list of contract issues (empty = valid)."""
        issues: list[str] = []
        for name, spec in self.agents.items():
            inv = spec.get("invocation")
            if not isinstance(inv, list) or not inv:
                issues.append(f"agents.{name}.invocation must be a non-empty list")
        if self.default_agent not in self.agents:
            issues.append(f"default_agent '{self.default_agent}' not in agents")
        if self.supervisor_agent not in self.agents:
            issues.append(f"supervisor_agent '{self.supervisor_agent}' not in agents")
        return issues

    def to_dict(self) -> dict:
        return self.data


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursive dict merge — override wins; nested dicts merge per-key."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_contract(project_root: str | Path = ".") -> OrchestrationContract:
    """Load the merged contract for a project (file optional)."""
    defaults = copy.deepcopy(DEFAULT_CONTRACT)
    path = Path(project_root) / CONTRACT_RELPATH
    if path.exists():
        try:
            user_data: Any = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in {path}: {exc}") from exc
        if not isinstance(user_data, dict):
            raise ValueError(f"{path}: contract root must be a JSON object")
        return OrchestrationContract(_deep_merge(defaults, user_data))
    return OrchestrationContract(defaults)
