"""Dashboard telemetry rollup matches persisted agent JSON snapshots."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.telemetry import aggregate_pipeline_telemetry  # noqa: E402


def test_platform_desk_billed_token_totals() -> None:
    rollup = aggregate_pipeline_telemetry("platform-desk")
    assert len(rollup["agents"]) == 4
    assert rollup["totals"]["inputTokens"] == 25208
    assert rollup["totals"]["outputTokens"] == 101611
    assert rollup["totals"]["totalTokens"] == 126819


def test_contacts_api_excludes_non_mvp_security_telemetry() -> None:
    """Security-agent telemetry exists on disk but is outside the MVP pipeline."""
    rollup = aggregate_pipeline_telemetry("contacts-api")
    assert len(rollup["agents"]) == 0


def test_change_request_hub_developer_billed_tokens() -> None:
    rollup = aggregate_pipeline_telemetry("change-request-hub")
    assert len(rollup["agents"]) >= 1
    dev = next(a for a in rollup["agents"] if a["agent"] == "developer-agent")
    assert int(dev["inputTokens"]) + int(dev["outputTokens"]) == 65947
