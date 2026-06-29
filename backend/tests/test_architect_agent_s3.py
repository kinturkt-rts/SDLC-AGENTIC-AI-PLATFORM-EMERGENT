"""Tests for architect-agent S3 pipeline (AgentCore A2A path)."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENT_PATH = _REPO_ROOT / "agents" / "architect-agent" / "architect_agent.py"


def _load_agent_module():
    spec = importlib.util.spec_from_file_location("architect_agent", _AGENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {_AGENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(_REPO_ROOT / "agents"))
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def local_artifact_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "local")


def test_enrich_architect_context_merges_run_context(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    from _shared.artifact_store import put_context

    put_context(
        "run-arch",
        {
            "targetApp": "demo-api",
            "runId": "run-arch",
            "prdPath": "docs/PRD/demo-api.md",
        },
    )
    mod = _load_agent_module()
    ctx = mod.enrich_architect_context({"runId": "run-arch"}, task="Design demo-api")
    assert ctx["targetApp"] == "demo-api"
    assert ctx["prdPath"] == "docs/PRD/demo-api.md"
    assert ctx.get("designDocPath")


def test_run_architect_from_context_persists_artifacts(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    from _shared.artifact_store import get_artifact, get_artifact_text, put_artifact
    from _shared.pipeline_context import design_doc_rel_for_app, diagram_path_for_app

    run_id = "run-arch-002"
    slug = "demo-api"
    diagram_rel = diagram_path_for_app(slug)
    design_rel = design_doc_rel_for_app(slug)
    put_artifact(run_id, "docs/PRD/demo-api.md", "# Demo PRD\n")
    mod = _load_agent_module()

    fake_png = repo_root / "tmp-diagram.png"
    fake_png.parent.mkdir(parents=True, exist_ok=True)
    fake_png.write_bytes(b"\x89PNG\r\n")

    fake_design = repo_root / design_rel
    fake_design.parent.mkdir(parents=True, exist_ok=True)
    fake_design.write_text("# Demo — Solution Design\n\n## 1. Summary\nShort.\n", encoding="utf-8")

    with patch.object(
        mod,
        "run_task",
        return_value=("diagram ok", [fake_png], fake_design),
    ):
        summary = mod.run_architect_from_context(
            "Produce architecture for demo-api",
            {
                "targetApp": "demo-api",
                "runId": run_id,
                "prdPath": "docs/PRD/demo-api.md",
            },
        )

    assert "Architecture artifacts created for demo-api" in summary
    assert get_artifact(run_id, diagram_rel).startswith(b"\x89PNG")
    assert "Solution Design" in get_artifact_text(run_id, design_rel)
    run_ctx = json.loads(get_artifact_text(run_id, "context.json"))
    assert run_ctx["targetApp"] == "demo-api"
    assert run_ctx.get("diagramPaths")


def test_build_architect_pipeline_agent_stream_async(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    mod = _load_agent_module()

    message = (
        "Produce architecture for demo-api\n\nContext:\n"
        + json.dumps({"targetApp": "demo-api", "runId": "run-a2a", "prdPath": "docs/PRD/demo-api.md"})
    )

    with patch.object(
        mod,
        "run_architect_from_context",
        return_value="Architecture artifacts created for demo-api.",
    ):
        agent = mod.build_architect_pipeline_agent([])

        async def collect_events() -> list[dict]:
            events: list[dict] = []
            async for event in agent.stream_async([{"text": message}]):
                events.append(event)
            return events

        events = asyncio.run(collect_events())

    assert any("result" in event for event in events)
    assert "Architecture artifacts created" in str(events[-1]["result"])


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    (tmp_path / "agents").mkdir()
    return tmp_path
