"""Tests for database-agent S3 artifact writes."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENT_PATH = _REPO_ROOT / "agents" / "database-agent" / "database_agent.py"


def _load_agent_module():
    sys.modules.pop("database_agent", None)
    spec = importlib.util.spec_from_file_location("database_agent", _AGENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {_AGENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(_REPO_ROOT / "agents"))
    spec.loader.exec_module(module)
    return module


def test_db_write_file_persists_to_s3_when_run_id_set(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REPO_ROOT", str(repo_root))
    monkeypatch.setenv("ARTIFACT_STORE", "local")
    (repo_root / "target-apps" / "demo-api" / "db" / "sql").mkdir(parents=True)

    mod = _load_agent_module()
    run_id = "db-write-001"
    mod._run_context = {"targetApp": "demo-api", "runId": run_id}

    result = mod.db_write_file(
        "target-apps/demo-api/db/sql/001_users.sql",
        "CREATE TABLE users (id uuid PRIMARY KEY);",
    )
    assert "Wrote target-apps/demo-api/db/sql/001_users.sql" in result

    from _shared.artifact_store import get_artifact_text

    stored = get_artifact_text(run_id, "target-apps/demo-api/db/sql/001_users.sql")
    assert "CREATE TABLE users" in stored
    mod._run_context = None


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    (tmp_path / "agents").mkdir()
    return tmp_path
