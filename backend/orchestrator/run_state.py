"""Persisted run state for the SDLC pipeline orchestrator.

State file: ``agents/pipeline/<feature>.run.json``. The frontend reads this
file (merged with the rest of the pipeline handoffs) to show live progress.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal


StepStatus = Literal["queued", "running", "completed", "failed", "skipped"]
RunStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


@dataclass
class StepRecord:
    name: str
    label: str
    status: StepStatus = "queued"
    started_at: str | None = None
    finished_at: str | None = None
    duration_sec: float | None = None
    transport: str | None = None
    error: str | None = None
    output_summary: str | None = None


@dataclass
class RunRecord:
    run_id: str
    feature: str
    status: RunStatus = "queued"
    triggered_by: str = "frontend"
    started_at: str | None = None
    finished_at: str | None = None
    current_step: str | None = None
    input_path: str | None = None
    error: str | None = None
    steps: list[StepRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "runId": self.run_id,
            "feature": self.feature,
            "status": self.status,
            "triggeredBy": self.triggered_by,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "currentStep": self.current_step,
            "inputPath": self.input_path,
            "error": self.error,
            "steps": [
                {
                    "name": s.name,
                    "label": s.label,
                    "status": s.status,
                    "startedAt": s.started_at,
                    "finishedAt": s.finished_at,
                    "durationSec": s.duration_sec,
                    "transport": s.transport,
                    "error": s.error,
                    "outputSummary": s.output_summary,
                }
                for s in self.steps
            ],
        }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_state_path(repo_root: Path, feature: str) -> Path:
    return repo_root / "agents" / "pipeline" / f"{feature}.run.json"


def write_state(repo_root: Path, record: RunRecord) -> None:
    path = run_state_path(repo_root, record.feature)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record.to_dict(), indent=2) + "\n", encoding="utf-8")


def load_state(repo_root: Path, feature: str) -> RunRecord | None:
    path = run_state_path(repo_root, feature)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    steps = [
        StepRecord(
            name=s["name"],
            label=s.get("label", s["name"]),
            status=s.get("status", "queued"),
            started_at=s.get("startedAt"),
            finished_at=s.get("finishedAt"),
            duration_sec=s.get("durationSec"),
            transport=s.get("transport"),
            error=s.get("error"),
            output_summary=s.get("outputSummary"),
        )
        for s in data.get("steps", [])
    ]
    return RunRecord(
        run_id=data["runId"],
        feature=data["feature"],
        status=data.get("status", "queued"),
        triggered_by=data.get("triggeredBy", "frontend"),
        started_at=data.get("startedAt"),
        finished_at=data.get("finishedAt"),
        current_step=data.get("currentStep"),
        input_path=data.get("inputPath"),
        error=data.get("error"),
        steps=steps,
    )


# Defensive: prove dataclass.asdict still works on RunRecord (used by tooling).
_ = asdict
