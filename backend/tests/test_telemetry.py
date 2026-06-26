"""Tests for agents/_shared/telemetry.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.telemetry import (  # noqa: E402
    RunTelemetry,
    aggregate_pipeline_telemetry,
    discover_agents_with_telemetry,
    short_model_label,
)


def test_short_model_label_sonnet_and_opus() -> None:
    assert short_model_label("us.anthropic.claude-sonnet-4-6") == "sonnet-4-6"
    assert short_model_label("us.anthropic.claude-opus-4-6") == "opus-4-6"


def test_run_telemetry_records_usage() -> None:
    tel = RunTelemetry("developer-agent", target_app="demo-app", model_id="opus-model")
    tel.record_usage({"inputTokens": 100, "outputTokens": 50, "totalTokens": 150})
    data = tel.to_dict()
    assert data["inputTokens"] == 100
    assert data["outputTokens"] == 50
    assert data["totalTokens"] == 150
    assert data["modelLabel"] == "opus"


def test_run_telemetry_print_compact() -> None:
    import io

    tel = RunTelemetry("product-agent", target_app="demo-app", model_id="sonnet-model")
    tel.record_usage({"inputTokens": 1000, "outputTokens": 200})
    buf = io.StringIO()
    tel.print_compact(stream=buf)
    out = buf.getvalue()
    assert "[product-agent]" in out
    assert "in=1,000" in out
    assert "out=200" in out


def test_aggregate_pipeline_telemetry(tmp_path: Path, monkeypatch) -> None:
    pipeline_dir = tmp_path / "pipeline"
    pipeline_dir.mkdir()
    import _shared.telemetry as tel_mod

    monkeypatch.setattr(tel_mod, "_PIPELINE_DIR", pipeline_dir)

    (pipeline_dir / "demo-app.product-agent-telemetry.json").write_text(
        json.dumps(
            {
                "agent": "product-agent",
                "inputTokens": 1000,
                "outputTokens": 500,
                "totalTokens": 1500,
                "elapsedSec": 10.0,
                "modelLabel": "sonnet-4-6",
            }
        ),
        encoding="utf-8",
    )
    (pipeline_dir / "demo-app.developer-agent-telemetry.json").write_text(
        json.dumps(
            {
                "agent": "developer-agent",
                "inputTokens": 2000,
                "outputTokens": 800,
                "totalTokens": 2800,
                "elapsedSec": 20.0,
                "modelLabel": "opus-4-6",
            }
        ),
        encoding="utf-8",
    )

    rollup = aggregate_pipeline_telemetry(
        "demo-app",
        ["product-agent", "architect-agent", "developer-agent"],
    )
    assert len(rollup["agents"]) == 2
    assert rollup["totals"]["inputTokens"] == 3000
    assert rollup["totals"]["outputTokens"] == 1300
    assert rollup["totals"]["totalTokens"] == 4300
    assert discover_agents_with_telemetry("demo-app") == ["product-agent", "developer-agent"]
