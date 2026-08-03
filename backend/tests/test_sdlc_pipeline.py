"""Tests for SDLC pipeline planner, transport resolution, and RDS apply."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agents._shared.a2a_invoke import a2a_invoke_error
from agents._shared.a2a_registry import parse_peer_url_overrides
from agents._shared.artifact_store import artifact_paths_for_agent, put_artifact, run_sql_artifact_keys
from agents._shared.sdlc_pipeline import (
    PIPELINE_STEPS,
    PipelineOptions,
    PipelineStepError,
    SdlcPipelineRunner,
    parse_pipeline_request,
    options_from_dict,
    planned_steps,
    resolve_transport,
)


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    (tmp_path / "agents").mkdir()
    (tmp_path / "scripts").mkdir()
    return tmp_path


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


def test_planned_steps_gitlab_only_when_developer_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_S3_BUCKET", "test-bucket")
    options = PipelineOptions(
        target_app="pr-diff-summarizer",
        skip_product=True,
        skip_architect=True,
        skip_db=True,
        skip_developer=True,
        skip_gitlab=False,
        transport="a2a",
    )
    steps = planned_steps(options)
    assert steps == ["gitlab-agent"]


def test_artifact_paths_for_product_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "local")
    monkeypatch.delenv("ARTIFACT_S3_BUCKET", raising=False)
    monkeypatch.delenv("ARTIFACT_STORE_S3_BUCKET", raising=False)
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
        "docs/generated-diagrams/expense-tracker.png"
    ]


def test_sync_delivery_profile_survives_hydrate_run_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Regression: deliveryProfile computed by _sync_delivery_profile() must not be
    wiped by a later _hydrate_run_context() call (as _step_architect/_step_developer
    do for a2a/S3 runs) — otherwise requiresStreamlit never reaches architect/developer
    and the Streamlit UI silently gets dropped from cloud pipeline runs."""
    from agents._shared.artifact_store import put_context
    from agents._shared.delivery_profile import sync_context_delivery_profile
    from agents._shared.sdlc_pipeline import PipelineOptions, SdlcPipelineRunner

    monkeypatch.setenv("ARTIFACT_STORE", "local")
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    monkeypatch.setattr("agents._shared.artifact_store.is_s3_store", lambda: False)
    (tmp_path / "agents" / "pipeline").mkdir(parents=True)
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs" / "fitness-tracker.txt").write_text(
        "Must have for v1: Streamlit UI under ui/streamlit_app.py.", encoding="utf-8"
    )

    run_id = "smoke-delivery-profile"
    put_context(run_id, {"targetApp": "fitness-tracker", "runId": run_id})

    options = PipelineOptions(
        target_app="fitness-tracker",
        run_id=run_id,
        transport="a2a",
        input_file="inputs/fitness-tracker.txt",
        skip_product=True,
        skip_architect=True,
        skip_db=True,
        skip_developer=True,
        skip_gitlab=True,
        skip_verify=True,
    )
    runner = SdlcPipelineRunner(options)
    runner._load_context()

    def fake_run_python(args: list[str], *, step: str) -> None:
        sync_context_delivery_profile(
            runner.root, runner.ctx_path, input_path="inputs/fitness-tracker.txt"
        )

    monkeypatch.setattr(runner, "_run_python", fake_run_python)
    runner._sync_delivery_profile("inputs/fitness-tracker.txt")

    assert runner.context["deliveryProfile"]["requiresStreamlit"] is True

    # Simulate what _step_architect() does immediately afterward.
    runner._hydrate_run_context()

    assert runner.context["deliveryProfile"]["requiresStreamlit"] is True


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
    monkeypatch.setattr("agents._shared.sdlc_pipeline.load_repo_env", lambda: None)
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


def test_update_run_json_preserves_triggered_by_seeded_in_s3(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The AgentCore container running a step has its own empty local disk on its
    first run.json write - it must pull the S3 copy the frontend already seeded
    (with triggeredBy) as the merge base, or that attribution is silently dropped
    the moment this container's first status update lands (the 'every run shows
    Frontend' bug)."""
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    monkeypatch.setattr("agents._shared.sdlc_pipeline.load_repo_env", lambda: None)
    (tmp_path / "agents" / "pipeline").mkdir(parents=True)

    run_id = "trig-by-run"
    seeded = {
        "runId": run_id,
        "feature": "expense-tracker",
        "targetApp": "expense-tracker",
        "triggeredBy": "kintur.shah@resolvetech.com",
        "startedAt": "2026-08-03T14:00:00+00:00",
        "status": "running",
        "steps": [{"name": "product-agent", "label": "1/6", "status": "queued"}],
    }

    def fake_get_artifact_text(rid: str, rel: str) -> str:
        assert (rid, rel) == (run_id, "run.json")
        return json.dumps(seeded)

    captured = {}

    def fake_put_artifact(rid, rel, body, **kwargs):
        captured["data"] = json.loads(body)

    monkeypatch.setattr("agents._shared.artifact_store.get_artifact_text", fake_get_artifact_text)
    monkeypatch.setattr("agents._shared.sdlc_pipeline.put_artifact", fake_put_artifact)

    options = PipelineOptions(target_app="expense-tracker", run_id=run_id, transport="a2a")
    runner = SdlcPipelineRunner(options)
    runner._update_run_json(status="running", current_step="product-agent")

    assert captured["data"]["triggeredBy"] == "kintur.shah@resolvetech.com"


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


# ── RDS apply (AgentCore / S3 materialize path) ───────────────────────────────


def test_run_sql_artifact_keys_filters_sql(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    monkeypatch.setenv("ARTIFACT_STORE", "local")
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
    put_artifact(run_id, "context.json", json.dumps({"targetApp": "inventory-app", "runId": run_id}))

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


def test_step_rds_apply_fails_on_seed_materialize_error(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seed materialize failure aborts the pipeline (no silent soft-fail)."""
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
        patch(
            "agents._shared.sdlc_pipeline.write_db_handoff",
            return_value="desk-booking/db/HANDOFF.md",
        ),
        patch("agents._shared.sdlc_pipeline.put_context"),
    ):
        workspace = repo_root / "workspace"
        sql_dir = workspace / "desk-booking" / "db" / "sql"
        sql_dir.mkdir(parents=True)
        resolve_ws.return_value = (workspace, sql_dir)
        with pytest.raises(PipelineStepError, match="seed-materialize failed"):
            runner._step_rds_apply()


def test_step_rds_apply_soft_fails_seed_materialize_when_env_opt_in(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Soft-fail only when explicitly opted in via env var."""
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    monkeypatch.setenv("ARTIFACT_STORE", "local")
    monkeypatch.setenv("SDLC_PIPELINE_TRANSPORT", "a2a")
    monkeypatch.setenv("SDLC_SOFT_FAIL_SEED_MATERIALIZE", "true")
    run_id = "run-db-005"

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
        patch(
            "agents._shared.sdlc_pipeline.write_db_handoff",
            return_value="desk-booking/db/HANDOFF.md",
        ) as handoff,
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


def test_step_developer_a2a_waits_for_handoff(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cloud developer step must wait for developer-handoff after A2A invoke returns."""
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_S3_BUCKET", "test-bucket")
    monkeypatch.setenv("SDLC_PIPELINE_TRANSPORT", "a2a")

    runner = object.__new__(SdlcPipelineRunner)
    runner.transport = "a2a"
    runner.run_id = "run-dev-wait-001"
    runner.feature = "demo-api"
    runner.root = repo_root
    runner.context = {"targetApp": "demo-api", "runId": runner.run_id}
    runner.options = PipelineOptions(target_app="demo-api", transport="a2a")
    runner.agents_run = []
    runner.artifacts = {}

    with (
        patch.object(runner, "_hydrate_run_context"),
        patch.object(runner, "_invoke_a2a") as invoke_mock,
        patch.object(runner, "_wait_for_developer_handoff") as wait_mock,
        patch.object(runner, "_merge_run_context_from_s3"),
        patch.object(runner, "_ensure_developer_telemetry"),
        patch.object(runner, "_after_agent_step"),
    ):
        runner._step_developer()

    invoke_mock.assert_called_once()
    wait_mock.assert_called_once()
    assert "developer-agent" in runner.agents_run


def _make_a2a_developer_runner(repo_root: Path, run_id: str) -> SdlcPipelineRunner:
    runner = object.__new__(SdlcPipelineRunner)
    runner.transport = "a2a"
    runner.run_id = run_id
    runner.feature = "demo-api"
    runner.root = repo_root
    runner.context = {"targetApp": "demo-api", "runId": run_id}
    runner.options = PipelineOptions(target_app="demo-api", transport="a2a")
    runner.agents_run = []
    runner.artifacts = {}
    return runner


def test_step_developer_retries_with_fallback_model(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First developer failure retries once with the lightweight fallback model."""
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_S3_BUCKET", "test-bucket")
    monkeypatch.setenv("SDLC_PIPELINE_TRANSPORT", "a2a")
    monkeypatch.setenv("SDLC_DEVELOPER_RETRY_ATTEMPTS", "1")
    monkeypatch.setenv("DEVELOPER_AGENT_FALLBACK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")

    runner = _make_a2a_developer_runner(repo_root, "run-dev-retry-001")

    calls: list[dict] = []

    def invoke_side_effect(agent_name, task, **kwargs):
        calls.append({"task": task, **kwargs})
        if len(calls) == 1:
            raise PipelineStepError("developer-agent A2A failed: boom")

    with (
        patch.object(runner, "_hydrate_run_context"),
        patch.object(runner, "_invoke_a2a", side_effect=invoke_side_effect),
        patch.object(runner, "_wait_for_developer_handoff"),
        patch.object(runner, "_merge_run_context_from_s3"),
        patch.object(runner, "_ensure_developer_telemetry"),
        patch.object(runner, "_after_agent_step"),
    ):
        runner._step_developer()

    assert len(calls) == 2
    assert calls[0].get("extra_context") is None
    assert calls[1]["extra_context"] == {"codingModelOverride": "us.anthropic.claude-sonnet-4-6"}
    assert "RETRY NOTE" in calls[1]["task"]
    assert "developer-agent" in runner.agents_run


def _make_a2a_gitlab_runner(repo_root: Path, run_id: str) -> SdlcPipelineRunner:
    runner = object.__new__(SdlcPipelineRunner)
    runner.transport = "a2a"
    runner.run_id = run_id
    runner.feature = "demo-api"
    runner.root = repo_root
    runner.context = {"targetApp": "demo-api", "runId": run_id}
    runner.options = PipelineOptions(target_app="demo-api", transport="a2a")
    runner.agents_run = []
    runner.artifacts = {}
    return runner


def test_step_gitlab_a2a_embeds_apps_layout_context(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A2A publish call must pass gitlabPublishLayout=apps (the default) via
    extra_context, not a hand-rolled Context: block in the task string - _invoke_a2a
    already appends its own single Context: block (targetApp/runId included via
    _context_for_agent); a second one in the task text would stack and break JSON
    parsing on gitlab-agent's receiving end (this was a real production bug)."""
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_S3_BUCKET", "test-bucket")
    monkeypatch.setenv("SDLC_PIPELINE_TRANSPORT", "a2a")
    monkeypatch.delenv("GITLAB_APPS_REPO", raising=False)

    runner = _make_a2a_gitlab_runner(repo_root, "run-gitlab-001")

    with (
        patch.object(runner, "_wait_for_developer_handoff"),
        patch.object(runner, "_invoke_a2a") as invoke_mock,
        patch.object(runner, "_read_gitlab_handoff", return_value={"status": "published"}),
        patch.object(runner, "_update_context"),
        patch.object(runner, "_after_agent_step"),
    ):
        runner._step_gitlab()

    invoke_mock.assert_called_once()
    task = invoke_mock.call_args.args[1]
    assert "Context:" not in task
    assert invoke_mock.call_args.kwargs["extra_context"] == {"gitlabPublishLayout": "apps"}
    assert "gitlab-agent" in runner.agents_run


def test_step_gitlab_a2a_respects_monorepo_opt_out(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GITLAB_APPS_REPO=false must still be honored for the A2A publish path."""
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_S3_BUCKET", "test-bucket")
    monkeypatch.setenv("SDLC_PIPELINE_TRANSPORT", "a2a")
    monkeypatch.setenv("GITLAB_APPS_REPO", "false")

    runner = _make_a2a_gitlab_runner(repo_root, "run-gitlab-002")

    with (
        patch.object(runner, "_wait_for_developer_handoff"),
        patch.object(runner, "_invoke_a2a") as invoke_mock,
        patch.object(runner, "_read_gitlab_handoff", return_value={"status": "published"}),
        patch.object(runner, "_update_context"),
        patch.object(runner, "_after_agent_step"),
    ):
        runner._step_gitlab()

    assert invoke_mock.call_args.kwargs["extra_context"] == {"gitlabPublishLayout": "monorepo"}


def test_step_developer_fails_after_all_retry_attempts(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When every attempt fails the step raises with the attempt count."""
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_S3_BUCKET", "test-bucket")
    monkeypatch.setenv("SDLC_PIPELINE_TRANSPORT", "a2a")
    monkeypatch.setenv("SDLC_DEVELOPER_RETRY_ATTEMPTS", "1")

    runner = _make_a2a_developer_runner(repo_root, "run-dev-retry-002")

    with (
        patch.object(runner, "_hydrate_run_context"),
        patch.object(
            runner,
            "_invoke_a2a",
            side_effect=PipelineStepError("developer-agent A2A failed: boom"),
        ) as invoke_mock,
        patch.object(runner, "_wait_for_developer_handoff"),
        patch.object(runner, "_merge_run_context_from_s3"),
        patch.object(runner, "_ensure_developer_telemetry"),
        patch.object(runner, "_after_agent_step"),
        pytest.raises(PipelineStepError, match="failed after 2 attempt"),
    ):
        runner._step_developer()

    assert invoke_mock.call_count == 2
    assert "developer-agent" not in runner.agents_run


def test_step_developer_handoff_timeout_triggers_retry(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing developer handoff (timeout) also re-invokes the developer agent."""
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_S3_BUCKET", "test-bucket")
    monkeypatch.setenv("SDLC_PIPELINE_TRANSPORT", "a2a")
    monkeypatch.setenv("SDLC_DEVELOPER_RETRY_ATTEMPTS", "1")

    runner = _make_a2a_developer_runner(repo_root, "run-dev-retry-003")

    wait_results = [PipelineStepError("developer-agent handoff not ready"), None]

    def wait_side_effect():
        result = wait_results.pop(0)
        if result is not None:
            raise result

    with (
        patch.object(runner, "_hydrate_run_context"),
        patch.object(runner, "_invoke_a2a") as invoke_mock,
        patch.object(runner, "_wait_for_developer_handoff", side_effect=wait_side_effect),
        patch.object(runner, "_merge_run_context_from_s3"),
        patch.object(runner, "_ensure_developer_telemetry"),
        patch.object(runner, "_after_agent_step"),
    ):
        runner._step_developer()

    assert invoke_mock.call_count == 2
    assert "developer-agent" in runner.agents_run
