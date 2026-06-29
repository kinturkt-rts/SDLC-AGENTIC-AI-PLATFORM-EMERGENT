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


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    (tmp_path / "agents").mkdir()
    return tmp_path
