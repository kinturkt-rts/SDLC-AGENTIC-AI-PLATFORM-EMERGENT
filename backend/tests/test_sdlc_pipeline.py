"""Tests for SDLC pipeline planner and transport resolution."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agents._shared.a2a_invoke import a2a_invoke_error
from agents._shared.a2a_registry import parse_peer_url_overrides
from agents._shared.artifact_store import artifact_paths_for_agent
from agents._shared.sdlc_pipeline import (
    PIPELINE_STEPS,
    PipelineOptions,
    parse_pipeline_request,
    options_from_dict,
    planned_steps,
    resolve_transport,
)


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
        {"prdPath": "target-apps/demo-api/prd/demo-api.md"},
    )
    assert paths == [
        "target-apps/demo-api/prd/demo-api.md",
        "target-apps/demo-api/agents/pipeline/demo-api.context.json",
    ]


def test_resolve_transport_explicit_local() -> None:
    assert resolve_transport("local") == "local"


def test_resolve_transport_from_s3_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.delenv("AGENTCORE_A2A_PEER_URLS", raising=False)
    assert resolve_transport("auto") == "a2a"


def test_resolve_transport_from_peer_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTCORE_A2A_PEER_URLS", "product-agent=https://x.example")
    assert resolve_transport("auto") == "a2a"


def test_a2a_invoke_error_detects_failed_task() -> None:
    result = {
        "status": "success",
        "response": {
            "kind": "task",
            "status": {
                "state": "failed",
                "message": {
                    "parts": [{"kind": "text", "text": "Agent execution failed"}],
                },
            },
        },
    }
    assert a2a_invoke_error(result) == "Agent execution failed"


def test_hydrate_run_context_uses_docs_layout_from_s3(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from agents._shared.artifact_store import put_context
    from agents._shared.sdlc_pipeline import PipelineOptions, SdlcPipelineRunner

    monkeypatch.setenv("ARTIFACT_STORE", "local")
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    monkeypatch.setattr("agents._shared.artifact_store.is_s3_store", lambda: False)
    (tmp_path / "agents" / "pipeline").mkdir(parents=True)

    run_id = "smoke-hydrate"
    put_context(
        run_id,
        {
            "targetApp": "expense-tracker",
            "runId": run_id,
            "inputFile": "inputs/expense-tracker.txt",
            "prdPath": "docs/PRD/expense-tracker.md",
            "designDocPath": "target-apps/expense-tracker/design/expense-tracker.md",
        },
    )

    options = PipelineOptions(
        target_app="expense-tracker",
        run_id=run_id,
        transport="a2a",
        skip_product=True,
        skip_architect=True,
        skip_db=True,
        skip_developer=True,
        skip_gitlab=True,
        skip_verify=True,
    )
    runner = SdlcPipelineRunner(options)
    runner._hydrate_run_context()

    assert runner.context["prdPath"] == "docs/PRD/expense-tracker.md"
    assert runner.context["inputFile"] == "inputs/expense-tracker.txt"
    assert runner.context["designDocPath"] == "docs/design/expense-tracker.md"
    assert runner.context["diagramPaths"] == [
        "docs/diagrams/generated-diagrams/expense-tracker.png"
    ]


def test_step_product_uses_prd_path_from_s3_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Orchestrator must trust specialist-written context.json paths (docs vs target-app-root)."""
    from agents._shared.artifact_store import put_artifact, put_context
    from agents._shared.sdlc_pipeline import PipelineOptions, SdlcPipelineRunner

    monkeypatch.setenv("ARTIFACT_STORE", "local")
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    (tmp_path / "agents" / "pipeline").mkdir(parents=True)

    run_id = "smoke-layout"
    put_artifact(run_id, "inputs/expense-tracker.txt", "brief")
    put_artifact(run_id, "docs/PRD/expense-tracker.md", "# PRD\n")
    put_context(
        run_id,
        {
            "targetApp": "expense-tracker",
            "prdPath": "docs/PRD/expense-tracker.md",
            "inputFile": "inputs/expense-tracker.txt",
        },
    )

    options = PipelineOptions(
        target_app="expense-tracker",
        input_file="inputs/expense-tracker.txt",
        run_id=run_id,
        transport="a2a",
        skip_architect=True,
        skip_db=True,
        skip_developer=True,
        skip_gitlab=True,
        skip_verify=True,
    )
    runner = SdlcPipelineRunner(options)
    runner.context = {"targetApp": "expense-tracker", "runId": run_id}
    runner.ctx_path = tmp_path / "agents/pipeline/expense-tracker.context.json"

    remote_ctx = {
        "targetApp": "expense-tracker",
        "runId": run_id,
        "prdPath": "docs/PRD/expense-tracker.md",
        "inputFile": "inputs/expense-tracker.txt",
    }

    def fake_get_artifact(run_id: str, rel: str) -> bytes:
        if rel == "docs/PRD/expense-tracker.md":
            return b"# PRD\n"
        if rel == "context.json":
            return json.dumps(remote_ctx).encode("utf-8")
        raise FileNotFoundError(rel)

    with patch.object(runner, "_invoke_a2a"):
        with patch(
            "agents._shared.artifact_store.get_context",
            return_value=remote_ctx,
        ):
            with patch(
                "agents._shared.artifact_store.get_artifact",
                side_effect=fake_get_artifact,
            ):
                runner._step_product()

    assert runner.context["prdPath"] == "docs/PRD/expense-tracker.md"
    assert "product-agent" in runner.agents_run


def test_options_from_dict_maps_run_id() -> None:
    opts = options_from_dict(
        {
            "targetApp": "team-faq-bot",
            "runId": "smoke-004",
            "inputFile": "inputs/team-faq-bot.txt",
            "transport": "a2a",
            "skip_db": True,
        }
    )
    assert opts.target_app == "team-faq-bot"
    assert opts.run_id == "smoke-004"
    assert opts.input_file == "inputs/team-faq-bot.txt"
    assert opts.skip_db is True


def test_after_agent_step_merges_remote_context_before_put(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from agents._shared.artifact_store import get_context, put_context
    from agents._shared.sdlc_pipeline import PipelineOptions, SdlcPipelineRunner

    monkeypatch.setenv("ARTIFACT_STORE", "local")
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    (tmp_path / "agents" / "pipeline").mkdir(parents=True)

    run_id = "after-db-merge"
    options = PipelineOptions(
        target_app="expense-tracker",
        run_id=run_id,
        transport="a2a",
        skip_product=True,
        skip_architect=True,
        skip_db=True,
        skip_developer=True,
        skip_gitlab=True,
        skip_verify=True,
    )
    runner = SdlcPipelineRunner(options)
    runner.context = {
        "targetApp": "expense-tracker",
        "runId": run_id,
        "prdPath": "docs/PRD/expense-tracker.md",
    }
    runner.ctx_path = tmp_path / "agents/pipeline/expense-tracker.context.json"

    put_context(
        run_id,
        {
            "targetApp": "expense-tracker",
            "dbOutputDir": "target-apps/expense-tracker/db",
            "preferredSqlPath": "target-apps/expense-tracker/db/sql",
        },
    )
    runner._after_agent_step("database-agent")

    loaded = get_context(run_id)
    assert loaded is not None
    assert loaded["prdPath"] == "docs/PRD/expense-tracker.md"
    assert loaded["dbOutputDir"] == "target-apps/expense-tracker/db"
    assert loaded["preferredSqlPath"] == "target-apps/expense-tracker/db/sql"


def test_parse_pipeline_request_from_a2a_message() -> None:
    message = (
        "Run run_sdlc_pipeline with:\n\n"
        + '{"target_app": "team-faq-bot", "run_id": "smoke-004", '
        '"input_file": "inputs/team-faq-bot.txt", "transport": "a2a", '
        '"skip_db": true}'
    )
    opts = parse_pipeline_request(message)
    assert opts is not None
    assert opts.target_app == "team-faq-bot"
    assert opts.run_id == "smoke-004"
    assert opts.transport == "a2a"
