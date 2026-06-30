"""Tests for agents/_shared/artifact_store.py (local mode)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def local_artifact_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "local")


def test_put_and_get_artifact_local(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    from _shared.artifact_store import get_artifact, put_artifact

    run_id = "test-run-001"
    put_artifact(run_id, "prd/demo.md", "# Demo PRD\n")
    body = get_artifact(run_id, "prd/demo.md")
    assert body.decode("utf-8") == "# Demo PRD\n"


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
