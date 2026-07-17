"""Tests for database-agent S3 artifact writes."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENT_PATH = _REPO_ROOT / "agents" / "database-agent" / "database_agent.py"

# Use a fixture slug — never "demo-api" — so a missed monkeypatch cannot recreate
# the deleted stale target-apps/demo-api/ tree on disk.
_FIXTURE_APP = "fixture-app"


def _load_agent_module():
    sys.modules.pop("database_agent", None)
    spec = importlib.util.spec_from_file_location("database_agent", _AGENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {_AGENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(_REPO_ROOT / "agents"))
    spec.loader.exec_module(module)
    return module


def _isolate_agent_paths(mod, repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep db_write_file off the real target-apps/ tree (module uses Path(__file__), not REPO_ROOT)."""
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    monkeypatch.setattr(mod, "_REPO_ROOT", repo_root)
    monkeypatch.setattr(mod, "_TARGET_APPS", repo_root / "target-apps")


def test_db_write_file_rewrites_target_apps_path_in_cloud_s3(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "local")

    mod = _load_agent_module()
    _isolate_agent_paths(mod, repo_root, monkeypatch)
    mod._run_context = {"targetApp": _FIXTURE_APP, "runId": "db-write-cloud-001"}
    captured: list[str] = []

    def _capture_write(rel: str, content: str, *, context: dict | None = None) -> str:
        captured.append(rel)
        return rel

    with patch.object(mod, "write_repo_artifact", side_effect=_capture_write):
        with patch.object(mod, "_is_cloud_store", return_value=True):
            with patch("_shared.pipeline_context._is_cloud_store", return_value=True):
                result = mod.db_write_file(
                    f"target-apps/{_FIXTURE_APP}/db/sql/001_users.sql",
                    "CREATE TABLE users (id uuid PRIMARY KEY);",
                )

    assert f"Wrote {_FIXTURE_APP}/db/sql/001_users.sql" in result
    assert captured == [f"{_FIXTURE_APP}/db/sql/001_users.sql"]
    mod._run_context = None


def test_db_write_file_cloud_requires_run_id(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module()
    _isolate_agent_paths(mod, repo_root, monkeypatch)
    mod._run_context = None
    captured: list[str] = []

    def _capture_write(rel: str, content: str, *, context: dict | None = None) -> str:
        captured.append(rel)
        return rel

    with patch.object(mod, "write_repo_artifact", side_effect=_capture_write):
        with patch.object(mod, "_is_cloud_store", return_value=True):
            with patch("_shared.pipeline_context._is_cloud_store", return_value=True):
                no_ctx = mod.db_write_file(
                    f"target-apps/{_FIXTURE_APP}/db/sql/001_users.sql",
                    "CREATE TABLE users (id uuid PRIMARY KEY);",
                )
                mod._run_context = {"targetApp": _FIXTURE_APP}
                no_run = mod.db_write_file(
                    f"target-apps/{_FIXTURE_APP}/db/sql/001_users.sql",
                    "CREATE TABLE users (id uuid PRIMARY KEY);",
                )

    assert no_ctx.startswith("Error:")
    assert "run context" in no_ctx
    assert no_run.startswith("Error:")
    assert "runId" in no_run
    assert captured == []
    mod._run_context = None


def test_db_validate_sql_cloud_loads_run_artifacts(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module()
    _isolate_agent_paths(mod, repo_root, monkeypatch)
    run_id = "db-validate-cloud-001"
    mod._run_context = {"targetApp": _FIXTURE_APP, "runId": run_id}
    key = f"{_FIXTURE_APP}/db/sql/010_seed.sql"
    bad_seed = (
        "INSERT INTO chunks (id, embedding) VALUES\n"
        "('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',\n"
        " (SELECT array_to_string(array_fill(0.01::float, ARRAY[8]), ','))::vector);\n"
    )

    with patch.object(mod, "_is_cloud_store", return_value=True):
        with patch.object(
            mod,
            "run_sql_artifact_keys",
            return_value=[key],
        ):
            with patch.object(mod, "get_artifact", return_value=bad_seed.encode("utf-8")):
                result = mod.db_validate_sql(_FIXTURE_APP)

    assert "SQL_VALIDATION FAILED" in result
    assert "array_to_string" in result
    mod._run_context = None


def test_db_validate_sql_cloud_rejects_bare_csv_vector_before_apply(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P1: cloud validate must catch the seed form that previously failed only at RDS apply."""
    mod = _load_agent_module()
    _isolate_agent_paths(mod, repo_root, monkeypatch)
    run_id = "db-validate-cloud-002"
    mod._run_context = {"targetApp": _FIXTURE_APP, "runId": run_id}
    key = f"{_FIXTURE_APP}/db/sql/010_seed.sql"
    # Same class of failure as safety-playbook-rag: text that is not '[…]' form.
    bad_seed = (
        "INSERT INTO chunks (id, embedding) VALUES\n"
        "('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '0.01,0.01,0.01'::vector);\n"
    )

    with patch.object(mod, "_is_cloud_store", return_value=True):
        with patch.object(mod, "run_sql_artifact_keys", return_value=[key]):
            with patch.object(mod, "get_artifact", return_value=bad_seed.encode("utf-8")):
                agent_result = mod.db_validate_sql(_FIXTURE_APP)

    assert "SQL_VALIDATION FAILED" in agent_result
    assert "missing leading '['" in agent_result

    # Host apply uses the same validator — ensure it would also block.
    from _shared.validate_sql_artifacts import validate_sql_dir

    sql_dir = repo_root / "sql"
    sql_dir.mkdir()
    (sql_dir / "010_seed.sql").write_text(bad_seed, encoding="utf-8")
    host_errors = validate_sql_dir(sql_dir)
    assert any("missing leading '['" in e for e in host_errors)
    mod._run_context = None


def test_db_validate_sql_local_still_works(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module()
    _isolate_agent_paths(mod, repo_root, monkeypatch)
    sql_dir = repo_root / "target-apps" / _FIXTURE_APP / "db" / "sql"
    sql_dir.mkdir(parents=True)
    (sql_dir / "001_users.sql").write_text(
        "CREATE TABLE users (id uuid PRIMARY KEY, name text NOT NULL);\n",
        encoding="utf-8",
    )
    (sql_dir / "010_seed.sql").write_text(
        "INSERT INTO users (id, name) VALUES\n"
        "('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'alice');\n",
        encoding="utf-8",
    )
    mod._run_context = {"targetApp": _FIXTURE_APP}

    with patch.object(mod, "_is_cloud_store", return_value=False):
        result = mod.db_validate_sql(_FIXTURE_APP)

    assert "SQL_VALIDATION OK" in result
    mod._run_context = None


def test_db_write_file_persists_to_s3_when_run_id_set(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "local")
    (repo_root / "target-apps" / _FIXTURE_APP / "db" / "sql").mkdir(parents=True)

    mod = _load_agent_module()
    _isolate_agent_paths(mod, repo_root, monkeypatch)
    run_id = "db-write-001"
    mod._run_context = {"targetApp": _FIXTURE_APP, "runId": run_id}

    result = mod.db_write_file(
        f"target-apps/{_FIXTURE_APP}/db/sql/001_users.sql",
        "CREATE TABLE users (id uuid PRIMARY KEY);",
    )
    assert f"Wrote target-apps/{_FIXTURE_APP}/db/sql/001_users.sql" in result

    from _shared.artifact_store import get_artifact_text

    stored = get_artifact_text(run_id, f"target-apps/{_FIXTURE_APP}/db/sql/001_users.sql")
    assert "CREATE TABLE users" in stored
    mod._run_context = None


def test_build_database_pipeline_agent_calls_run_task(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    import json

    mod = _load_agent_module()
    _isolate_agent_paths(mod, repo_root, monkeypatch)

    message = (
        "Design database schema\n\nContext:\n"
        + json.dumps(
            {
                "targetApp": _FIXTURE_APP,
                "runId": "run-db-a2a",
                "designDocPath": f"docs/design/{_FIXTURE_APP}.md",
            }
        )
    )
    captured: dict[str, object] = {}

    def fake_run_task(task, context=None, **kwargs):
        captured["task"] = task
        captured["context"] = context
        captured["kwargs"] = kwargs
        return ("schema ok", [f"target-apps/{_FIXTURE_APP}/db/sql/001.sql"])

    class FakeShellAgent:
        def __call__(self, *args, **kwargs):
            return ""

        async def stream_async(self, *args, **kwargs):
            if False:
                yield {}

    with patch.object(mod, "run_task", side_effect=fake_run_task):
        with patch.object(mod, "_build_agent", return_value=FakeShellAgent()):
            agent = mod.build_database_pipeline_agent([])

        async def collect_events() -> list[dict]:
            events: list[dict] = []
            async for event in agent.stream_async([{"text": message}]):
                events.append(event)
            return events

        events = asyncio.run(collect_events())

    assert captured["context"]["runId"] == "run-db-a2a"  # type: ignore[index]
    assert any("result" in event for event in events)
    assert "schema ok" in str(events[-1]["result"])
    assert "001.sql" in str(events[-1]["result"])


def test_database_pipeline_surfaces_run_task_errors(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module()
    _isolate_agent_paths(mod, repo_root, monkeypatch)

    with patch.object(mod, "run_task", side_effect=RuntimeError("bedrock unavailable")):
        text = mod._execute_database_pipeline_message(
            "task\n\nContext:\n" + f'{{"targetApp":"{_FIXTURE_APP}","runId":"r1"}}',
        )

    assert "Database pipeline could not start" in text
    assert "bedrock unavailable" in text


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    (tmp_path / "agents").mkdir()
    (tmp_path / "target-apps").mkdir()
    return tmp_path
