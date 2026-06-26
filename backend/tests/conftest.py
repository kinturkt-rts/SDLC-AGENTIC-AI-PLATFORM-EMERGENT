"""Shared fixtures for repo-root platform tests (agents/_shared, scripts)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared import env as shared_env  # noqa: E402

# Keys from .env.local that make unit tests non-deterministic when load_repo_env runs.
_ISOLATED_ENV_KEYS = (
    "DATABASE_URL",
    "POSTGRES_APP_SCHEMA",
    "POSTGRES_MCP_DB_ENDPOINT",
    "POSTGRES_MCP_DATABASE",
    "POSTGRES_MCP_DB_USER",
    "POSTGRES_MCP_DB_PASSWORD",
    "POSTGRES_MCP_PORT",
    "POSTGRES_MCP_REGION",
    "POSTGRES_MCP_SSLMODE",
    "POSTGRES_MCP_CONNECTION_METHOD",
    "POSTGRES_MCP_DEPLOYMENT",
    "POSTGRES_MCP_INSTANCE_IDENTIFIER",
    "POSTGRES_MCP_CLUSTER_IDENTIFIER",
    "POSTGRES_MCP_SECRET_ARN",
    "SEED_MIN_ROWS",
    "SEED_MAX_ROWS",
)


@pytest.fixture(autouse=True)
def isolate_local_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent .env.local from clobbering monkeypatched env in unit tests."""
    monkeypatch.setattr(shared_env, "load_repo_env", lambda: None)
    for key in _ISOLATED_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
