"""Tests for product-agent PRD pipeline (local + S3 artifact paths)."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENT_PATH = _REPO_ROOT / "agents" / "product-agent" / "product_agent.py"


def _load_agent_module():
    spec = importlib.util.spec_from_file_location("product_agent", _AGENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {_AGENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(_REPO_ROOT / "agents"))
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def local_artifact_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "local")


def test_prd_rel_path_defaults_to_target_app() -> None:
    from _shared.pipeline_context import prd_rel_path_for_app

    assert prd_rel_path_for_app("inventory-app") == (
        "target-apps/inventory-app/docs/PRD/inventory-app.md"
    )


def test_resolve_input_text_from_inline(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    mod = _load_agent_module()
    text = mod.resolve_input_text({"inputText": "Build a widget catalog."})
    assert text == "Build a widget catalog."


def test_resolve_input_text_from_s3_run(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    from _shared.artifact_store import put_artifact

    mod = _load_agent_module()
    put_artifact("run-abc", "inputs/demo.txt", "Warehouse brief body")
    text = mod.resolve_input_text(
        {"runId": "run-abc", "inputFile": "inputs/demo.txt"},
    )
    assert "Warehouse brief" in text


def test_run_prd_from_context_writes_target_app_layout(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    mod = _load_agent_module()

    fake_prd = "# Demo App\n\n## 1. Overview\nShort.\n"
    with patch.object(mod, "_generate_prd_from_text", return_value=fake_prd):
        summary = mod.run_prd_from_context(
            "Create PRD",
            {
                "targetApp": "demo-api",
                "inputText": "A tiny API for demos.",
                "runId": "run-001",
            },
        )

    prd_path = (
        repo_root
        / "agents/pipeline/runs/run-001/target-apps/demo-api/docs/PRD/demo-api.md"
    )
    ctx_path = (
        repo_root
        / "agents/pipeline/runs/run-001/target-apps/demo-api/agents/pipeline/demo-api.context.json"
    )
    run_ctx_path = repo_root / "agents/pipeline/runs/run-001/context.json"

    assert prd_path.is_file()
    assert run_ctx_path.is_file()
    assert not ctx_path.is_file()
    assert "prdPath: target-apps/demo-api/docs/PRD/demo-api.md" in summary

    ctx = json.loads(run_ctx_path.read_text(encoding="utf-8"))
    assert ctx["targetApp"] == "demo-api"
    assert ctx["prdPath"] == "target-apps/demo-api/docs/PRD/demo-api.md"


def test_enrich_prd_context_infers_target_and_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module()
    monkeypatch.delenv("PIPELINE_RUN_ID", raising=False)
    ctx = mod.enrich_prd_context({}, task="Create PRD from staged input for inventory-app.")
    assert ctx["targetApp"] == "inventory-app"
    assert ctx["inputFile"] == "inputs/inventory-app.txt"


def test_enrich_prd_context_uses_pipeline_run_id_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module()
    monkeypatch.setenv("PIPELINE_RUN_ID", "smoke-001")
    ctx = mod.enrich_prd_context(
        {"targetApp": "inventory-app"},
        task="Create PRD",
    )
    assert ctx["runId"] == "smoke-001"
    assert ctx["inputFile"] == "inputs/inventory-app.txt"


def test_parse_task_and_context() -> None:
    mod = _load_agent_module()
    task, ctx = mod.parse_task_and_context(
        "Create PRD\n\nContext:\n{\"targetApp\": \"inventory-app\"}"
    )
    assert task == "Create PRD"
    assert ctx["targetApp"] == "inventory-app"


def test_build_prd_pipeline_agent_stream_async_writes_artifacts(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AgentCore A2A uses stream_async; it must run the PRD pipeline and persist artifacts."""
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    mod = _load_agent_module()

    fake_prd = "# Demo App\n\n## 1. Overview\nShort.\n"
    message = (
        "Create PRD\n\nContext:\n"
        + json.dumps(
            {
                "targetApp": "demo-api",
                "inputText": "A tiny API for demos.",
                "runId": "run-a2a",
            }
        )
    )

    with patch.object(mod, "_generate_prd_from_text", return_value=fake_prd):
        agent = mod.build_prd_pipeline_agent()

        async def collect_events() -> list[dict]:
            events: list[dict] = []
            async for event in agent.stream_async([{"text": message}]):
                events.append(event)
            return events

        events = asyncio.run(collect_events())

    assert any("result" in event for event in events)
    result_text = str(events[-1]["result"])
    assert "PRD created for demo-api" in result_text
    assert (
        repo_root
        / "agents/pipeline/runs/run-a2a/target-apps/demo-api/docs/PRD/demo-api.md"
    ).is_file()
    assert (repo_root / "agents/pipeline/runs/run-a2a/context.json").is_file()


def test_health_check_message_skips_prd_pipeline() -> None:
    mod = _load_agent_module()
    result = mod._execute_prd_pipeline_message(
        "Control-plane health check only. Reply with exactly: OK",
    )
    assert result == "OK"


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    (tmp_path / "agents").mkdir()
    return tmp_path
