"""Tests for agents/_shared/artifact_store.py (local mode)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def local_artifact_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "local")
    monkeypatch.delenv("ARTIFACT_S3_BUCKET", raising=False)
    monkeypatch.delenv("ARTIFACT_STORE_S3_BUCKET", raising=False)


def test_put_and_get_artifact_local(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    from _shared.artifact_store import get_artifact, put_artifact

    run_id = "test-run-001"
    put_artifact(run_id, "prd/demo.md", "# Demo PRD\n")
    body = get_artifact(run_id, "prd/demo.md")
    assert body.decode("utf-8") == "# Demo PRD\n"


@pytest.mark.parametrize(
    "rel",
    [
        "_template/app/main.py",
        "target-apps/_template/scaffold-manifest.json",
    ],
)
def test_put_artifact_rejects_template_paths(
    rel: str,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    from _shared.artifact_store import put_artifact

    with pytest.raises(ValueError, match="Templates belong under templates"):
        put_artifact("run-template-leak", rel, "must not be stored")


def test_put_and_get_context_local(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    from _shared.artifact_store import get_context, put_context

    run_id = "test-run-002"
    ctx = {"targetApp": "demo-api", "prdPath": "prd/demo-api.md"}
    put_context(run_id, ctx)
    loaded = get_context(run_id)
    assert loaded is not None
    assert loaded["targetApp"] == "demo-api"
    assert loaded["runId"] == run_id


def test_put_context_merges_existing(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    from _shared.artifact_store import get_context, put_context

    run_id = "test-run-merge"
    put_context(run_id, {"targetApp": "demo-api", "prdPath": "docs/PRD/demo-api.md"})
    put_context(run_id, {"designDocPath": "docs/design/demo-api.md", "dbOutputDir": "target-apps/demo-api/db"})
    loaded = get_context(run_id)
    assert loaded is not None
    assert loaded["targetApp"] == "demo-api"
    assert loaded["prdPath"] == "docs/PRD/demo-api.md"
    assert loaded["designDocPath"] == "docs/design/demo-api.md"
    assert loaded["dbOutputDir"] == "target-apps/demo-api/db"


def test_put_context_strips_runtime_fields_on_persist(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    from _shared.artifact_store import get_context, put_context

    run_id = "test-run-sanitize"
    put_context(
        run_id,
        {
            "targetApp": "demo-api",
            "prdPath": "docs/PRD/demo-api.md",
            "inputPath": "inputs/demo-api.txt",
            "diagramOutputDir": "/tmp/generated-diagrams",
            "productAgentOutput": "See prdPath for demo-api MVP requirements.",
            "architectSummary": "summary text",
        },
    )
    loaded = get_context(run_id)
    assert loaded is not None
    assert loaded["inputFile"] == "inputs/demo-api.txt"
    assert "inputPath" not in loaded
    assert "diagramOutputDir" not in loaded
    assert "architectSummary" not in loaded
    assert "productAgentOutput" not in loaded


def test_enrich_db_paths_from_run(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    from _shared.artifact_store import enrich_db_paths_from_run, put_artifact

    run_id = "test-run-db-paths"
    put_artifact(run_id, "target-apps/expense-tracker/db/sql/001_init.sql", "SELECT 1;")
    ctx = enrich_db_paths_from_run(
        {"runId": run_id, "targetApp": "expense-tracker"},
    )
    assert ctx["preferredSqlPath"] == "target-apps/expense-tracker/db/sql"
    assert ctx["dbOutputDir"] == "target-apps/expense-tracker/db"


def test_artifact_paths_for_developer(repo_root: Path) -> None:
    from _shared.artifact_store import artifact_paths_for_agent

    paths = artifact_paths_for_agent("developer-agent", "my-app", {})
    assert paths == ["target-apps/my-app"]


def test_artifact_paths_for_frontend(repo_root: Path) -> None:
    from _shared.artifact_store import artifact_paths_for_agent

    paths = artifact_paths_for_agent("frontend-agent", "my-app", {})
    assert paths == ["target-apps/my-app/frontend"]


def test_artifact_paths_for_frontend_matches_local_write_dir_in_s3_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """frontend_agent.py always writes to the literal target-apps/<slug>/frontend dir
    on local disk, regardless of ARTIFACT_STORE. Guard against regressing to
    target_app_root_rel() (which drops the "target-apps/" prefix when
    ARTIFACT_STORE=s3) — that would silently desync sync_repo_paths_to_run's local
    read from the agent's real write location and upload nothing."""
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_S3_BUCKET", "test-bucket")
    from _shared.artifact_store import artifact_paths_for_agent

    paths = artifact_paths_for_agent("frontend-agent", "my-app", {})
    assert paths == ["target-apps/my-app/frontend"]


def test_sync_frontend_paths_to_run_uploads_to_s3(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proves the orchestrator's existing S3-mode sync (artifact_paths_for_agent +
    sync_repo_paths_to_run, already called from sdlc_pipeline._after_agent_step for
    every agent) now actually uploads frontend-agent's output, instead of silently
    syncing zero files because "frontend-agent" had no branch."""
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_S3_BUCKET", "test-bucket")

    frontend_dir = repo_root / "target-apps" / "my-app" / "frontend"
    (frontend_dir / "src" / "components").mkdir(parents=True)
    (frontend_dir / "package.json").write_text("{}", encoding="utf-8")
    (frontend_dir / "src" / "App.tsx").write_text("export default App;", encoding="utf-8")
    (frontend_dir / "src" / "components" / "List.tsx").write_text("List", encoding="utf-8")

    from _shared.artifact_store import artifact_paths_for_agent, sync_repo_paths_to_run

    paths = artifact_paths_for_agent("frontend-agent", "my-app", {})
    assert paths == ["target-apps/my-app/frontend"]

    with patch("_shared.artifact_store._s3_client") as mock_client_factory:
        mock_client = mock_client_factory.return_value
        synced = sync_repo_paths_to_run("run-frontend-001", paths)

    uploaded_keys = {call.kwargs["Key"] for call in mock_client.put_object.call_args_list}
    assert uploaded_keys == {
        "runs/run-frontend-001/target-apps/my-app/frontend/package.json",
        "runs/run-frontend-001/target-apps/my-app/frontend/src/App.tsx",
        "runs/run-frontend-001/target-apps/my-app/frontend/src/components/List.tsx",
    }
    for call in mock_client.put_object.call_args_list:
        assert call.kwargs["Bucket"] == "test-bucket"
    assert set(synced) == {
        "target-apps/my-app/frontend/package.json",
        "target-apps/my-app/frontend/src/App.tsx",
        "target-apps/my-app/frontend/src/components/List.tsx",
    }


def test_write_repo_artifact_local(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    from _shared.artifact_store import get_artifact_text, read_repo_artifact, write_repo_artifact

    rel = "docs/PRD/local-only.md"
    write_repo_artifact(rel, "hello")
    assert read_repo_artifact(rel).decode("utf-8") == "hello"

    run_id = "run-write-001"
    run_rel = "target-apps/demo/db/sql/001.sql"
    write_repo_artifact(run_rel, "SELECT 1;", context={"runId": run_id})
    assert get_artifact_text(run_id, run_rel) == "SELECT 1;"


def test_dynamodb_enabled_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARTIFACT_DYNAMODB_ENABLED", raising=False)
    from _shared.artifact_store import dynamodb_enabled

    assert dynamodb_enabled() is False


def test_put_dynamodb_pointer_skipped_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_DYNAMODB_ENABLED", "false")
    from _shared.artifact_store import _put_dynamodb_pointer

    with patch("_shared.artifact_store._dynamodb_table") as mock_table:
        _put_dynamodb_pointer("run-1", "docs/PRD/demo.md", s3_uri="s3://bucket/runs/run-1/docs/PRD/demo.md")
        mock_table.assert_not_called()


def test_update_pipeline_run_no_op_when_dynamodb_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_DYNAMODB_ENABLED", "false")
    from _shared.artifact_store import update_pipeline_run

    with patch("_shared.artifact_store._dynamodb_table") as mock_table:
        applied = update_pipeline_run("run-1", status="failed", pipeline_id=5)
        mock_table.assert_not_called()
        assert applied is True


def test_update_pipeline_run_includes_condition_expression_with_pipeline_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_DYNAMODB_ENABLED", "true")
    from _shared.artifact_store import update_pipeline_run

    with patch("_shared.artifact_store._dynamodb_table") as mock_table:
        applied = update_pipeline_run(
            "run-1", status="completed", last_agent="devops-agent", pipeline_id=42
        )
        assert applied is True
        _, kwargs = mock_table.return_value.update_item.call_args
        assert kwargs["ConditionExpression"] == "attribute_not_exists(#p) OR #p <= :p"
        assert kwargs["ExpressionAttributeValues"][":p"] == 42


def test_update_pipeline_run_omits_condition_expression_without_pipeline_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_DYNAMODB_ENABLED", "true")
    from _shared.artifact_store import update_pipeline_run

    with patch("_shared.artifact_store._dynamodb_table") as mock_table:
        applied = update_pipeline_run("run-1", status="completed")
        assert applied is True
        _, kwargs = mock_table.return_value.update_item.call_args
        assert "ConditionExpression" not in kwargs


def test_update_pipeline_run_rejects_stale_pipeline_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pipeline that finishes late for a superseded commit must not clobber a
    status already recorded by a newer pipeline (the run-582cf1e8 stale-write bug)."""
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_DYNAMODB_ENABLED", "true")
    from botocore.exceptions import ClientError

    from _shared.artifact_store import update_pipeline_run

    with patch("_shared.artifact_store._dynamodb_table") as mock_table:
        mock_table.return_value.update_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "stale"}},
            "UpdateItem",
        )
        applied = update_pipeline_run("run-1", status="failed", pipeline_id=3)
        assert applied is False


def test_update_pipeline_run_reraises_unrelated_client_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_DYNAMODB_ENABLED", "true")
    from botocore.exceptions import ClientError

    from _shared.artifact_store import update_pipeline_run

    with patch("_shared.artifact_store._dynamodb_table") as mock_table:
        mock_table.return_value.update_item.side_effect = ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "x"}},
            "UpdateItem",
        )
        with pytest.raises(ClientError):
            update_pipeline_run("run-1", status="failed", pipeline_id=3)


def test_materialize_run_local(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    from _shared.artifact_store import materialize_run, put_artifact

    run_id = "test-run-003"
    put_artifact(run_id, "context.json", json.dumps({"targetApp": "x"}))
    workspace = materialize_run(run_id)
    assert (workspace / "context.json").is_file()


def test_write_repo_artifact_skips_duplicate_pipeline_context_with_run_id(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    from _shared.artifact_store import get_artifact, put_context, write_repo_artifact

    run_id = "run-dedupe"
    put_context(run_id, {"targetApp": "expense-tracker", "prdPath": "docs/PRD/expense-tracker.md"})
    write_repo_artifact(
        "agents/pipeline/expense-tracker.context.json",
        '{"stale": true}\n',
        context={"runId": run_id},
    )

    body = get_artifact(run_id, "context.json").decode("utf-8")
    assert "expense-tracker" in body
    assert "stale" not in body
    with pytest.raises(FileNotFoundError):
        get_artifact(run_id, "agents/pipeline/expense-tracker.context.json")


def test_read_repo_artifact_resolves_pipeline_context_to_canonical(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    from _shared.artifact_store import put_context, read_repo_artifact

    run_id = "run-read-alias"
    put_context(run_id, {"targetApp": "demo-api", "prdPath": "docs/PRD/demo-api.md"})
    raw = read_repo_artifact(
        "agents/pipeline/demo-api.context.json",
        context={"runId": run_id},
    )
    assert json.loads(raw.decode("utf-8"))["targetApp"] == "demo-api"


def test_get_context_falls_back_to_legacy_per_app_path(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    from _shared.artifact_store import get_context, put_artifact
    from _shared.pipeline_context import pipeline_context_rel_for_app

    run_id = "run-legacy"
    legacy_rel = pipeline_context_rel_for_app("demo-api")
    put_artifact(
        run_id,
        legacy_rel,
        json.dumps({"targetApp": "demo-api", "prdPath": "docs/PRD/demo-api.md"}) + "\n",
    )
    loaded = get_context(run_id, target_app="demo-api")
    assert loaded is not None
    assert loaded["targetApp"] == "demo-api"


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    (tmp_path / "agents").mkdir()
    return tmp_path


def test_resolve_prd_artifact_rel_prefers_cloud_layout(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    from _shared.artifact_store import put_artifact, resolve_prd_artifact_rel

    run_id = "smoke-007"
    cloud_rel = "agent-ops-assistant/docs/PRD/agent-ops-assistant.md"
    put_artifact(run_id, cloud_rel, "# PRD\n")
    resolved = resolve_prd_artifact_rel(
        run_id,
        "agent-ops-assistant",
        {"prdPath": "target-apps/agent-ops-assistant/docs/PRD/agent-ops-assistant.md"},
    )
    assert resolved == cloud_rel


def test_get_artifact_s3_missing_key_raises_file_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_S3_BUCKET", "test-bucket")

    from botocore.exceptions import ClientError

    from _shared.artifact_store import get_artifact

    def _raise_no_such_key(*_args: object, **_kwargs: object) -> None:
        raise ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "GetObject",
        )

    with patch("_shared.artifact_store._s3_client") as mock_client:
        mock_client.return_value.get_object.side_effect = _raise_no_such_key
        with pytest.raises(FileNotFoundError, match="S3 artifact not found"):
            get_artifact("smoke-006", "docs/design/field-service-dispatch.md")


def test_wait_for_run_artifact_local(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    from _shared.artifact_store import put_artifact, run_artifact_exists, wait_for_run_artifact

    run_id = "wait-run-001"
    assert run_artifact_exists(run_id, "demo-app/handoffs/developer-handoff.json") is False
    put_artifact(run_id, "demo-app/handoffs/developer-handoff.json", '{"writtenFiles": []}\n')
    wait_for_run_artifact(run_id, "demo-app/handoffs/developer-handoff.json", timeout_sec=1.0)
    assert run_artifact_exists(run_id, "demo-app/handoffs/developer-handoff.json") is True


def test_wait_for_developer_handoff_local(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    from _shared.artifact_store import (
        developer_handoff_exists,
        put_artifact,
        wait_for_developer_handoff,
    )
    from _shared.pipeline_context import developer_handoff_rel_for_app

    run_id = "wait-dev-handoff-001"
    rel = developer_handoff_rel_for_app("demo-app")
    assert developer_handoff_exists(run_id, "demo-app") is False
    put_artifact(
        run_id,
        rel,
        '{"writtenFiles": ["target-apps/demo-app/app/main.py"], "status": "completed"}\n',
    )
    found = wait_for_developer_handoff(run_id, "demo-app", timeout_sec=1.0)
    assert found == rel
    assert developer_handoff_exists(run_id, "demo-app") is True


def test_wait_for_developer_handoff_ignores_in_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from _shared.artifact_store import wait_for_developer_handoff
    from _shared.pipeline_context import developer_handoff_rel_for_app

    responses = iter(
        [
            '{"status": "in_progress"}',
            '{"status": "completed"}',
        ]
    )
    with (
        patch("_shared.artifact_store.get_artifact_text", side_effect=lambda *_: next(responses)),
        patch("time.sleep"),
    ):
        rel = wait_for_developer_handoff(
            "run-in-progress",
            "demo-app",
            timeout_sec=1.0,
            poll_interval_sec=0.01,
        )
    assert rel == developer_handoff_rel_for_app("demo-app")


def test_wait_for_developer_handoff_surfaces_failure() -> None:
    from _shared.artifact_store import wait_for_developer_handoff

    with patch(
        "_shared.artifact_store.get_artifact_text",
        return_value='{"status": "failed", "error": "model timeout"}',
    ):
        with pytest.raises(RuntimeError, match="model timeout"):
            wait_for_developer_handoff("run-failed", "demo-app", timeout_sec=1.0)


def test_classify_developer_readiness_completed() -> None:
    from _shared.artifact_store import DEV_READY_COMPLETED, classify_developer_readiness

    with patch(
        "_shared.artifact_store.get_artifact_text",
        return_value='{"status": "completed", "writtenFiles": ["a.py"]}',
    ):
        decision, handoff = classify_developer_readiness(
            "run-1", "demo-app", timeout_sec=1.0, poll_interval_sec=0.01
        )
    assert decision == DEV_READY_COMPLETED
    assert handoff is not None


def test_classify_developer_readiness_failed() -> None:
    from _shared.artifact_store import DEV_READY_FAILED, classify_developer_readiness

    with patch(
        "_shared.artifact_store.get_artifact_text",
        return_value='{"status": "failed", "error": "boom"}',
    ):
        decision, handoff = classify_developer_readiness(
            "run-2", "demo-app", timeout_sec=1.0, poll_interval_sec=0.01
        )
    assert decision == DEV_READY_FAILED
    assert (handoff or {}).get("error") == "boom"


def test_classify_developer_readiness_partial_when_stalled_with_artifacts() -> None:
    """A stalled in_progress handoff with delivered app files publishes best-effort."""
    from _shared.artifact_store import DEV_READY_PARTIAL, classify_developer_readiness

    with (
        patch(
            "_shared.artifact_store.get_artifact_text",
            return_value='{"status": "in_progress", "writtenFiles": ["target-apps/demo-app/app/main.py"]}',
        ),
        patch(
            "_shared.artifact_store.list_run_artifact_keys",
            return_value=["demo-app/app/main.py", "demo-app/requirements.txt"],
        ),
        patch("time.sleep"),
    ):
        decision, handoff = classify_developer_readiness(
            "run-3", "demo-app", timeout_sec=5.0, poll_interval_sec=0.01, stall_polls=2
        )
    assert decision == DEV_READY_PARTIAL
    assert (handoff or {}).get("status") == "in_progress"


def test_classify_developer_readiness_missing_without_artifacts() -> None:
    """In_progress handoff but no publishable app files blocks publish."""
    from _shared.artifact_store import DEV_READY_MISSING, classify_developer_readiness

    with (
        patch(
            "_shared.artifact_store.get_artifact_text",
            return_value='{"status": "in_progress", "writtenFiles": []}',
        ),
        patch("_shared.artifact_store.list_run_artifact_keys", return_value=["demo-app/db/HANDOFF.md"]),
        patch("time.sleep"),
    ):
        decision, _ = classify_developer_readiness(
            "run-4", "demo-app", timeout_sec=5.0, poll_interval_sec=0.01, stall_polls=2
        )
    assert decision == DEV_READY_MISSING


def test_run_has_publishable_app_artifacts() -> None:
    from _shared.artifact_store import run_has_publishable_app_artifacts

    with patch(
        "_shared.artifact_store.list_run_artifact_keys",
        return_value=["demo-app/app/routers/x.py", "demo-app/db/HANDOFF.md"],
    ):
        assert run_has_publishable_app_artifacts("run-5", "demo-app") is True

    with patch(
        "_shared.artifact_store.list_run_artifact_keys",
        return_value=["demo-app/db/HANDOFF.md", "_template/app/main.py"],
    ):
        assert run_has_publishable_app_artifacts("run-6", "demo-app") is False
