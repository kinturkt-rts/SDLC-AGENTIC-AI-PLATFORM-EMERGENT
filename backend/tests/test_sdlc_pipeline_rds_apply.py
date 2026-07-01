"""Tests for AgentCore/S3 RDS apply path in sdlc_pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agents._shared.artifact_store import put_artifact, run_sql_artifact_keys
from agents._shared.sdlc_pipeline import PipelineOptions, PipelineStepError, SdlcPipelineRunner


@pytest.fixture(autouse=True)
def local_artifact_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "local")


def test_run_sql_artifact_keys_filters_sql(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    run_id = "run-db-001"
    put_artifact(run_id, "target-apps/demo-api/db/sql/001_users.sql", "CREATE TABLE users ();")
    put_artifact(run_id, "target-apps/demo-api/db/HANDOFF.md", "# handoff")
    put_artifact(run_id, "context.json", "{}")

    keys = run_sql_artifact_keys(run_id, "demo-api")
    assert keys == ["target-apps/demo-api/db/sql/001_users.sql"]


def test_resolve_rds_workspace_materializes_from_s3(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    monkeypatch.setenv("ARTIFACT_STORE", "local")
    monkeypatch.setenv("SDLC_PIPELINE_TRANSPORT", "a2a")
    run_id = "run-db-002"
    sql_body = "CREATE TABLE items (id uuid PRIMARY KEY);"
    put_artifact(run_id, "target-apps/inventory-app/db/sql/001_items.sql", sql_body)
    put_context = put_artifact
    put_context(run_id, "context.json", json.dumps({"targetApp": "inventory-app", "runId": run_id}))

    options = PipelineOptions(
        target_app="inventory-app",
        transport="a2a",
        run_id=run_id,
    )
    runner = object.__new__(SdlcPipelineRunner)
    runner.transport = "a2a"
    runner.run_id = run_id
    runner.feature = "inventory-app"
    runner.root = repo_root

    workspace, sql_dir = runner._resolve_rds_workspace()
    assert sql_dir.is_dir()
    assert (sql_dir / "001_items.sql").read_text(encoding="utf-8") == sql_body
    assert workspace != repo_root


def test_step_rds_apply_invokes_scripts_with_materialized_sql_dir(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    monkeypatch.setenv("ARTIFACT_STORE", "local")
    monkeypatch.setenv("SDLC_PIPELINE_TRANSPORT", "a2a")
    run_id = "run-db-003"
    put_artifact(run_id, "target-apps/demo-api/db/sql/001_init.sql", "SELECT 1;")

    options = PipelineOptions(
        target_app="demo-api",
        transport="a2a",
        run_id=run_id,
        skip_postgres=False,
    )
    runner = object.__new__(SdlcPipelineRunner)
    runner.transport = "a2a"
    runner.run_id = run_id
    runner.feature = "demo-api"
    runner.root = repo_root
    runner.context = {"targetApp": "demo-api", "runId": run_id}
    runner.ctx_path = repo_root / "agents" / "pipeline" / "demo-api.context.json"

    calls: list[list[str]] = []

    def fake_run_python(args: list[str], *, step: str) -> None:
        calls.append(args)

    with (
        patch.object(runner, "_run_python", side_effect=fake_run_python),
        patch.object(runner, "put_context", create=True),
        patch(
            "agents._shared.sdlc_pipeline.write_db_handoff",
            return_value="target-apps/demo-api/db/HANDOFF.md",
        ),
        patch("agents._shared.sdlc_pipeline.put_context"),
    ):
        runner._step_rds_apply()

    assert calls[0][0].endswith("apply_sql_to_rds.py")
    assert "--skip-seed-materialize" in calls[0]
    assert "--sql-dir" in calls[0]
    sql_dir = Path(calls[0][calls[0].index("--sql-dir") + 1])
    assert (sql_dir / "001_init.sql").is_file()
    assert not any(c[0].endswith("materialize_seed_passwords.py") for c in calls)


def test_step_rds_apply_soft_fails_seed_materialize_on_a2a(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    monkeypatch.setenv("ARTIFACT_STORE", "local")
    monkeypatch.setenv("SDLC_PIPELINE_TRANSPORT", "a2a")
    run_id = "run-db-004"

    runner = object.__new__(SdlcPipelineRunner)
    runner.transport = "a2a"
    runner.run_id = run_id
    runner.feature = "desk-booking"
    runner.root = repo_root
    runner.context = {"targetApp": "desk-booking", "runId": run_id}
    runner.ctx_path = repo_root / "agents" / "pipeline" / "desk-booking.context.json"

    def fake_run_python(args: list[str], *, step: str) -> None:
        if step == "seed-materialize":
            raise PipelineStepError("seed-materialize failed (exit 1): bad hash column")

    with (
        patch.object(runner, "_resolve_rds_workspace") as resolve_ws,
        patch.object(runner, "_run_python", side_effect=fake_run_python),
        patch(
            "agents._shared.seed_credentials.seed_sql_has_placeholders",
            return_value=True,
        ),
        patch.object(runner, "_save_context"),
        patch("agents._shared.sdlc_pipeline.write_db_handoff", return_value="desk-booking/db/HANDOFF.md") as handoff,
        patch("agents._shared.sdlc_pipeline.put_context"),
    ):
        workspace = repo_root / "workspace"
        sql_dir = workspace / "desk-booking" / "db" / "sql"
        sql_dir.mkdir(parents=True)
        resolve_ws.return_value = (workspace, sql_dir)
        runner._step_rds_apply()

    handoff.assert_called_once()
    assert handoff.call_args.kwargs["rds_applied"] is True
    assert "seedMaterializeWarning" in handoff.call_args.args[1]
    assert runner.context.get("databaseHandoffPath") == "desk-booking/db/HANDOFF.md"


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    (tmp_path / "agents").mkdir()
    (tmp_path / "scripts").mkdir()
    return tmp_path
