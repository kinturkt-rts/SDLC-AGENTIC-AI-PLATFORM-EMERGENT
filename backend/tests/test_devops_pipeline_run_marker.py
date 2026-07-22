"""Unit tests for devops-agent PIPELINE_RUN_ID marker fallback."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND / "agents"))
sys.path.insert(0, str(_BACKEND / "agents" / "devops-agent"))

import devops_agent as da  # noqa: E402


def test_ensure_pipeline_run_id_from_apps_repo_root_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(da, "_REPO_ROOT", tmp_path)
    monkeypatch.delenv("PIPELINE_RUN_ID", raising=False)
    marker = tmp_path / ".sdlc" / "pipeline-run.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(
        json.dumps({"runId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "targetApp": "demo"}),
        encoding="utf-8",
    )
    ctx: dict = {}
    da._ensure_pipeline_run_id_from_marker("demo", ctx)
    assert ctx["runId"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert da.os.environ["PIPELINE_RUN_ID"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_ensure_pipeline_run_id_prefers_target_apps_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(da, "_REPO_ROOT", tmp_path)
    monkeypatch.delenv("PIPELINE_RUN_ID", raising=False)
    root_marker = tmp_path / ".sdlc" / "pipeline-run.json"
    root_marker.parent.mkdir(parents=True)
    root_marker.write_text(json.dumps({"runId": "root-run-id"}), encoding="utf-8")
    app_marker = tmp_path / "target-apps" / "demo" / ".sdlc" / "pipeline-run.json"
    app_marker.parent.mkdir(parents=True)
    app_marker.write_text(json.dumps({"runId": "app-run-id"}), encoding="utf-8")
    ctx: dict = {}
    da._ensure_pipeline_run_id_from_marker("demo", ctx)
    assert ctx["runId"] == "app-run-id"
