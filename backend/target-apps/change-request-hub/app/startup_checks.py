"""Fail-fast runtime validation — catches misconfigured .env before routes return opaque 500s.

Call from FastAPI lifespan on startup (not at config import time) so pytest can use SQLite.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings


def _is_postgres_url(url: str) -> bool:
    if not url:
        return False
    return url.split(":", 1)[0].lower().startswith("postgres")


def _read_dotenv_value(key: str) -> str | None:
    """Read a single KEY=value from .env without loading it — just for diagnostics."""
    env_path = Path(".env")
    if not env_path.is_file():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        k, v = stripped.split("=", 1)
        if k.strip() == key:
            return v.strip()
    return None


def should_skip_startup_checks(settings: Settings) -> bool:
    """Skip strict checks during pytest and dev_validate_app import probes."""
    if os.environ.get("SKIP_STARTUP_CHECKS", "").strip().lower() in ("1", "true", "yes"):
        return True
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    return (settings.app_env or "").strip().lower() == "test"


def validate_runtime_config(settings: Settings) -> None:
    """Raise RuntimeError with actionable text when .env is missing or wrong DB driver."""
    if should_skip_startup_checks(settings):
        return

    url = (settings.database_url or "").strip()
    schema = (settings.postgres_schema or "public").strip()
    postgres_app = schema != "public" or _is_postgres_url(url)

    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and add a line like:\n"
            "  DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db?sslmode=require\n"
            "Each .env line must be KEY=value — never paste a bare URL without DATABASE_URL=."
        )

    if postgres_app and not _is_postgres_url(url):
        hint = ""
        shell_val = os.environ.get("DATABASE_URL", "")
        dotenv_val = _read_dotenv_value("DATABASE_URL") or ""
        if shell_val and shell_val.startswith("sqlite") and _is_postgres_url(dotenv_val):
            hint = (
                "\n\n*** ROOT CAUSE: Your .env has the correct Postgres URL, but a SHELL "
                "environment variable DATABASE_URL='{}' is overriding it. ***\n"
                "Fix: run this command in your terminal BEFORE uvicorn:\n"
                "  PowerShell:  Remove-Item Env:DATABASE_URL\n"
                "  Bash:        unset DATABASE_URL\n"
                "Or simply CLOSE this terminal and open a fresh one."
            ).format(shell_val[:60])
        raise RuntimeError(
            f"DATABASE_URL must use Postgres (postgresql+psycopg://...) for schema "
            f"'{schema}', but got: {url[:60]}...\n"
            "Fix .env: ensure the line starts with DATABASE_URL= and points to RDS."
            f"{hint}"
        )


def ping_database() -> None:
    """Verify DB connectivity — used by lifespan and GET /health."""
    from sqlalchemy import text

    from app.database import engine

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
