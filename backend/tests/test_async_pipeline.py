"""Tests for the fire-and-forget (async) pipeline paths.

Covers:
- _shared/background_tasks registry (drives HealthyBusy ping)
- orchestrator-agent async ack + background pipeline execution
- developer-agent async ack + initial in_progress handoff
- SdlcPipelineRunner run.json S3 mirror + default steps skeleton
"""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared import background_tasks


def _load_agent_module(folder: str, stem: str):
    path = _REPO_ROOT / "agents" / folder / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _wait_until(predicate, timeout_sec: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


# ── background task registry ────────────────────────────────────


def test_background_task_counter_begin_end() -> None:
    base = background_tasks.active_background_tasks()
    task_id = background_tasks.begin_background_task("test-task")
    assert background_tasks.active_background_tasks() == base + 1
    background_tasks.end_background_task(task_id)
    assert background_tasks.active_background_tasks() == base
    # idempotent
    background_tasks.end_background_task(task_id)
    assert background_tasks.active_background_tasks() == base


def test_run_in_background_executes_and_unregisters() -> None:
    base = background_tasks.active_background_tasks()
    done = threading.Event()
    thread = background_tasks.run_in_background("test-run", done.set)
    thread.join(timeout=5)
    assert done.is_set()
    assert _wait_until(lambda: background_tasks.active_background_tasks() == base)


def test_run_in_background_unregisters_on_crash() -> None:
    base = background_tasks.active_background_tasks()

    def _boom() -> None:
        raise RuntimeError("crash")

    thread = background_tasks.run_in_background("test-crash", _boom)
    thread.join(timeout=5)
    assert _wait_until(lambda: background_tasks.active_background_tasks() == base)


# ── orchestrator async entrypoint ───────────────────────────────


def test_orchestrator_async_ack_and_background_run(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module("orchestrator-agent", "orchestrator_agent")
    monkeypatch.setenv("AGENTCORE_ORCHESTRATOR_ASYNC", "1")

    from _shared import artifact_store

    monkeypatch.setattr(artifact_store, "is_s3_store", lambda: True)

    ran = threading.Event()
    captured: dict[str, Any] = {}

    def _fake_run(options):  # noqa: ANN001
        captured["run_id"] = options.run_id
        ran.set()

        class _Result:
            def summary(self) -> str:
                return "ok"

        return _Result()

    monkeypatch.setattr(mod, "run_sdlc_pipeline", _fake_run)

    payload = {
        "target_app": "async-test-app",
        "run_id": "async-run-001",
        "input_file": "inputs/async-test-app.txt",
        "transport": "a2a",
    }
    ack = mod._execute_pipeline_message(f"Run run_sdlc_pipeline with:\n\n{json.dumps(payload)}")

    assert "PIPELINE_ASYNC_STARTED" in ack
    assert "async-run-001" in ack
    assert "runs/async-run-001/run.json" in ack
    assert ran.wait(timeout=5)
    assert captured["run_id"] == "async-run-001"


def test_orchestrator_async_generates_run_id_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module("orchestrator-agent", "orchestrator_agent")
    monkeypatch.setenv("AGENTCORE_ORCHESTRATOR_ASYNC", "1")

    from _shared import artifact_store, sdlc_pipeline

    monkeypatch.setattr(artifact_store, "is_s3_store", lambda: True)
    monkeypatch.setattr(sdlc_pipeline, "mark_run_failed", lambda *_a, **_k: None)

    finished = threading.Event()

    def _fake_run(_options):  # noqa: ANN001
        finished.set()

        class _Result:
            def summary(self) -> str:
                return "ok"

        return _Result()

    monkeypatch.setattr(mod, "run_sdlc_pipeline", _fake_run)

    from _shared.sdlc_pipeline import PipelineOptions

    options = PipelineOptions(target_app="async-test-app")
    ack = mod._start_pipeline_async(options)
    assert ack is not None
    assert options.run_id, "async start must allocate a runId for the ack"
    assert options.run_id in ack
    assert finished.wait(timeout=5)


def test_orchestrator_sync_when_async_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module("orchestrator-agent", "orchestrator_agent")
    monkeypatch.setenv("AGENTCORE_ORCHESTRATOR_ASYNC", "0")

    from _shared.sdlc_pipeline import PipelineOptions

    assert mod._start_pipeline_async(PipelineOptions(target_app="x")) is None


def test_orchestrator_async_marks_run_failed_on_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module("orchestrator-agent", "orchestrator_agent")
    monkeypatch.setenv("AGENTCORE_ORCHESTRATOR_ASYNC", "1")

    from _shared import artifact_store, sdlc_pipeline

    monkeypatch.setattr(artifact_store, "is_s3_store", lambda: True)

    failed: dict[str, Any] = {}
    marked = threading.Event()

    def _fake_mark(run_id: str, target_app: str, error: str) -> None:
        failed.update({"run_id": run_id, "target_app": target_app, "error": error})
        marked.set()

    monkeypatch.setattr(sdlc_pipeline, "mark_run_failed", _fake_mark)

    def _crash(_options):  # noqa: ANN001
        raise RuntimeError("bedrock exploded")

    monkeypatch.setattr(mod, "run_sdlc_pipeline", _crash)

    from _shared.sdlc_pipeline import PipelineOptions

    options = PipelineOptions(target_app="async-test-app", run_id="async-run-002")
    ack = mod._start_pipeline_async(options)
    assert ack is not None
    assert marked.wait(timeout=5)
    assert failed["run_id"] == "async-run-002"
    assert "bedrock exploded" in failed["error"]


# ── developer async entrypoint ──────────────────────────────────


def test_developer_async_ack_writes_in_progress_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module("developer-agent", "developer_agent")
    monkeypatch.setenv("AGENTCORE_DEVELOPER_ASYNC", "1")
    monkeypatch.setattr(mod, "is_s3_store", lambda: True)

    handoffs: list[dict[str, Any]] = []

    def _fake_write(app: str, handoff: dict[str, Any], *, context=None) -> str:  # noqa: ANN001
        handoffs.append(handoff)
        return f"{app}/handoffs/developer-handoff.json"

    monkeypatch.setattr(mod, "_write_developer_handoff", _fake_write)

    ran = threading.Event()
    monkeypatch.setattr(mod, "run_task", lambda task, ctx: ran.set())

    ctx = {"targetApp": "async-test-app", "runId": "async-run-003"}
    message = f"Implement the app.\n\nContext:\n{json.dumps(ctx)}"
    ack = mod._execute_developer_pipeline_message(message)

    assert "PIPELINE_ASYNC_STARTED" in ack
    assert "async-run-003" in ack
    assert handoffs and handoffs[0]["status"] == "in_progress"
    assert handoffs[0]["asyncAccepted"] is True
    assert ran.wait(timeout=5)


def test_developer_sync_when_no_run_id(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module("developer-agent", "developer_agent")
    monkeypatch.setenv("AGENTCORE_DEVELOPER_ASYNC", "1")
    monkeypatch.setattr(mod, "is_s3_store", lambda: True)
    monkeypatch.delenv("PIPELINE_RUN_ID", raising=False)

    assert mod._start_developer_pipeline_async("task", {"targetApp": "x"}) is None


def test_developer_async_disabled_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module("developer-agent", "developer_agent")
    monkeypatch.setenv("AGENTCORE_DEVELOPER_ASYNC", "false")
    monkeypatch.setenv("AGENTCORE_AGENT", "developer-agent")
    assert mod._developer_async_enabled() is False
    monkeypatch.setenv("AGENTCORE_DEVELOPER_ASYNC", "true")
    assert mod._developer_async_enabled() is True
    monkeypatch.delenv("AGENTCORE_DEVELOPER_ASYNC", raising=False)
    assert mod._developer_async_enabled() is True  # implied by AGENTCORE_AGENT
    monkeypatch.delenv("AGENTCORE_AGENT", raising=False)
    assert mod._developer_async_enabled() is False


# ── run.json S3 mirror + steps skeleton ─────────────────────────


def test_update_run_json_seeds_steps_and_mirrors_to_s3(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from _shared import sdlc_pipeline as sp

    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(sp, "is_s3_store", lambda: True)
    monkeypatch.setattr(sp, "resolve_transport", lambda mode: "a2a")

    mirrored: dict[str, Any] = {}

    def _fake_put(run_id: str, rel: str, content: str, *, content_type=None) -> str:  # noqa: ANN001
        mirrored[rel] = json.loads(content)
        return rel

    monkeypatch.setattr(sp, "put_artifact", _fake_put)

    options = sp.PipelineOptions(
        target_app="async-test-app",
        run_id="async-run-004",
        transport="a2a",
        skip_verify=True,
    )
    runner = sp.SdlcPipelineRunner(options)
    runner._update_run_json(status="running", current_step="product-agent")

    local = tmp_path / "agents" / "pipeline" / "runs" / "async-run-004" / "run.json"
    assert local.is_file()
    data = json.loads(local.read_text(encoding="utf-8"))
    assert data["status"] == "running"
    assert data["currentStep"] == "product-agent"
    assert data["startedAt"]
    step_names = [s["name"] for s in data["steps"]]
    assert step_names == [
        "product-agent",
        "architect-agent",
        "database-agent",
        "developer-agent",
        "gitlab-agent",
        "qa-agent",
    ]
    statuses = {s["name"]: s["status"] for s in data["steps"]}
    assert statuses["product-agent"] == "running"
    assert statuses["qa-agent"] == "skipped"  # with_qa not set

    assert "run.json" in mirrored
    assert mirrored["run.json"]["status"] == "running"


def test_update_run_json_terminal_failed_marks_current_step(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from _shared import sdlc_pipeline as sp

    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(sp, "is_s3_store", lambda: False)

    options = sp.PipelineOptions(target_app="async-test-app", run_id="async-run-005")
    runner = sp.SdlcPipelineRunner(options)
    runner._update_run_json(status="running", current_step="developer-agent")
    runner._update_run_json(status="failed", error="boom", finished=True)

    local = tmp_path / "agents" / "pipeline" / "runs" / "async-run-005" / "run.json"
    data = json.loads(local.read_text(encoding="utf-8"))
    assert data["status"] == "failed"
    assert data["error"] == "boom"
    assert data["finishedAt"]
    statuses = {s["name"]: s["status"] for s in data["steps"]}
    assert statuses["developer-agent"] == "failed"
    assert statuses["product-agent"] == "completed"


def test_mark_run_failed_writes_terminal_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from _shared import sdlc_pipeline as sp

    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(sp, "is_s3_store", lambda: False)

    sp.mark_run_failed("async-run-006", "async-test-app", "orchestrator crashed: x")
    local = tmp_path / "agents" / "pipeline" / "runs" / "async-run-006" / "run.json"
    data = json.loads(local.read_text(encoding="utf-8"))
    assert data["status"] == "failed"
    assert "orchestrator crashed" in data["error"]
    assert data["finishedAt"]