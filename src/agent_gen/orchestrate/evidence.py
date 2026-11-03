"""Evidence persistence — every run leaves an auditable trail.

Layout: <evidence.dir>/<UTC-ts>-<workflow-name>/
    run.json                    RunResult (statuses, evidence, final workflow)
    steps/<id>-<attempt>.stdout
    steps/<id>-<attempt>.stderr
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .models import Evidence, RunResult


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w\-]", "-", name).strip("-") or "workflow"


class EvidenceSink:
    """Writes per-step outputs as they happen and run.json at the end."""

    def __init__(self, project_root: str | Path, evidence_dir: str, workflow_name: str):
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.run_dir = (
            Path(project_root) / evidence_dir / f"{ts}-{_safe_name(workflow_name)}"
        )
        self.steps_dir = self.run_dir / "steps"

    def write_step(self, ev: Evidence) -> None:
        self.steps_dir.mkdir(parents=True, exist_ok=True)
        base = self.steps_dir / f"{_safe_name(ev.step_id)}-{ev.attempt}"
        base.with_suffix(".stdout").write_text(ev.stdout, encoding="utf-8")
        base.with_suffix(".stderr").write_text(ev.stderr, encoding="utf-8")

    def finalize(self, result: RunResult) -> Path:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        run_path = self.run_dir / "run.json"
        run_path.write_text(
            json.dumps(result.to_dict(), indent=2), encoding="utf-8"
        )
        return run_path


class NullSink:
    """No-op sink for dry runs and library callers that persist elsewhere."""

    run_dir = None

    def write_step(self, ev: Evidence) -> None:  # noqa: ARG002
        return

    def finalize(self, result: RunResult) -> None:  # noqa: ARG002
        return None
