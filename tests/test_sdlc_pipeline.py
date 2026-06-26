"""Tests for SDLC pipeline planner and transport resolution."""

from __future__ import annotations

import pytest

from agents._shared.a2a_registry import parse_peer_url_overrides
from agents._shared.artifact_store import artifact_paths_for_agent
from agents._shared.sdlc_pipeline import PIPELINE_STEPS, PipelineOptions, planned_steps, resolve_transport


def test_parse_peer_url_overrides_named_pairs() -> None:
    raw = "product-agent=https://p.example,architect-agent=https://a.example"
    assert parse_peer_url_overrides(raw) == {
        "product-agent": "https://p.example",
        "architect-agent": "https://a.example",
    }


def test_pipeline_steps_match_diagram() -> None:
    assert PIPELINE_STEPS == (
        "product-agent",
        "architect-agent",
        "database-agent",
        "developer-agent",
        "gitlab-agent",
        "qa-agent",
    )


def test_planned_steps_full_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITLAB_PERSONAL_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("GITLAB_PROJECT_PATH", "group/project")
    options = PipelineOptions(
        target_app="inventory-app",
        input_file="inputs/inventory-app.txt",
    )
    steps = planned_steps(options)
    assert steps == [
        "product-agent",
        "architect-agent",
        "database-agent",
        "developer-agent",
        "gitlab-agent",
    ]
    assert "verify" not in steps


def test_planned_steps_qa_after_gitlab(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITLAB_PERSONAL_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("GITLAB_PROJECT_PATH", "group/project")
    options = PipelineOptions(
        target_app="inventory-app",
        input_file="inputs/inventory-app.txt",
        with_qa=True,
    )
    steps = planned_steps(options)
    assert steps[-2:] == ["gitlab-agent", "qa-agent"]


def test_planned_steps_skip_db_and_gitlab() -> None:
    options = PipelineOptions(
        target_app="demo-api",
        skip_db=True,
        skip_gitlab=True,
        skip_product=True,
        skip_architect=True,
        skip_verify=True,
    )
    steps = planned_steps(options)
    assert steps == ["developer-agent"]


def test_artifact_paths_for_product_agent() -> None:
    paths = artifact_paths_for_agent(
        "product-agent",
        "demo-api",
        {"prdPath": "docs/PRD/demo-api.md"},
    )
    assert paths == ["docs/PRD/demo-api.md"]


def test_resolve_transport_explicit_local() -> None:
    assert resolve_transport("local") == "local"


def test_resolve_transport_from_peer_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTCORE_A2A_PEER_URLS", "product-agent=https://x.example")
    assert resolve_transport("auto") == "a2a"
