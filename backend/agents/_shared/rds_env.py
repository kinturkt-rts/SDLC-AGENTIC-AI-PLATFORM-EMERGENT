"""Shared RDS connection env for apply, materialize, and verify scripts."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import dotenv_values

from _shared.env import load_repo_env

_REPO_ROOT = Path(__file__).resolve().parents[2]


def load_target_app_env(target_app: str, repo_root: Path | None = None) -> None:
    """Load repo .env/.env.local, then target-apps/<app>/.env (app wins for DATABASE_URL)."""
    load_repo_env()
    root = repo_root or _REPO_ROOT
    app_env = root / "target-apps" / target_app / ".env"
    if not app_env.is_file():
        return
    for key, value in dotenv_values(app_env).items():
        if value is not None and str(value).strip():
            os.environ[key] = str(value).strip()


def schema_for_app(target_app: str) -> str:
    """Postgres schema for target-apps/<slug> — must match apply_sql_to_rds.resolve_app_schema.

    Uses POSTGRES_APP_SCHEMA when set (e.g. by apply_sql_to_rds before materialize).
    Does NOT fall back to POSTGRES_SCHEMA from repo .env.local — that often points at a
    different app and causes materialize to UPDATE zero rows while seed SQL applied elsewhere.
    """
    explicit = os.environ.get("POSTGRES_APP_SCHEMA", "").strip()
    if explicit:
        return explicit
    return target_app.strip().replace("-", "_")


def connection_url() -> str:
    host = os.environ.get("POSTGRES_MCP_DB_ENDPOINT", "").strip()
    database = os.environ.get("POSTGRES_MCP_DATABASE", "").strip()
    user = os.environ.get("POSTGRES_MCP_DB_USER", "postgres").strip()
    password = os.environ.get("POSTGRES_MCP_DB_PASSWORD", "").strip()
    port = os.environ.get("POSTGRES_MCP_PORT", "5432").strip()
    sslmode = os.environ.get("POSTGRES_MCP_SSLMODE", "require").strip()

    if host and database and password:
        return (
            f"postgresql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{database}"
            f"?sslmode={sslmode}"
        )

    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url

    raise ValueError(
        "Set POSTGRES_MCP_* in repo .env.local or DATABASE_URL in target-apps/<app>/.env"
    )
