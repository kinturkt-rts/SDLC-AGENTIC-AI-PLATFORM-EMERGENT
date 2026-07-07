"""Unit tests for cloudwatch_logs helpers (parsing and run-id extraction)."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "agents"))

from _shared.cloudwatch_logs import (  # noqa: E402
    _extract_run_id,
    _message_matches_run,
    _parse_level,
    _run_filter_patterns,
    _strip_level_prefix,
)


def test_parse_level_from_python_logging_prefix() -> None:
    assert _parse_level("INFO:_shared.agentcore_serve:Starting server") == "info"
    assert _parse_level("WARNING:root:deprecated") == "warn"
    assert _parse_level("ERROR:orchestrator:boom") == "error"
    assert _parse_level("DEBUG:foo:trace") == "debug"
    assert _parse_level("CRITICAL:foo:bad") == "error"


def test_parse_level_infers_from_text() -> None:
    assert _parse_level("Traceback (most recent call last)") == "error"
    assert _parse_level("Something went wrong, warn user") == "warn"
    assert _parse_level("debug: extra detail") == "debug"
    assert _parse_level("All good") == "info"


def test_extract_run_id() -> None:
    assert _extract_run_id("run_id=abc-123 done") == "abc-123"
    assert _extract_run_id("run-id: smoke-004 starting") == "smoke-004"
    assert _extract_run_id("runId=92099e5f-be02-4894-9276-67f2e5a72343") == "92099e5f-be02-4894-9276-67f2e5a72343"
    assert _extract_run_id("no run id here") is None


def test_strip_level_prefix() -> None:
    assert _strip_level_prefix("INFO:_shared.agentcore_serve:Starting server") == "Starting server"
    assert _strip_level_prefix("ERROR:orchestrator:Failed handoff") == "Failed handoff"
    assert _strip_level_prefix("plain line") == "plain line"


def test_run_filter_patterns_includes_camel_and_snake() -> None:
    rid = "b605bf6a-784f-4fc1-a66d-b95ac026eff9"
    patterns = _run_filter_patterns(rid)
    assert f'"{rid}"' in patterns
    assert f'"run_id={rid}"' in patterns
    assert f'"runId={rid}"' in patterns


def test_message_matches_run_variants() -> None:
    rid = "b605bf6a-784f-4fc1-a66d-b95ac026eff9"
    assert not _message_matches_run("anything", None)
    assert _message_matches_run(f"runId={rid} starting product", rid)
    assert _message_matches_run(f"run_id={rid} done", rid)
    assert _message_matches_run(f"pipeline {rid} ok", rid)
    assert not _message_matches_run("unrelated log line", rid)
