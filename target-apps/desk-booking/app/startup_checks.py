"""Startup validation — fail-fast before serving traffic."""
from __future__ import annotations


def validate_runtime_config(settings) -> None:
    """Raise ValueError with actionable message if config is invalid."""
    if not settings.database_url:
        raise ValueError(
            "DATABASE_URL is required. Set it to a valid PostgreSQL connection string like:\n"
            "postgresql+psycopg://user:pass@host:5432/dbname?sslmode=require"
        )

    if settings.database_url.startswith("sqlite://") and settings.app_env != "test":
        raise ValueError(
            "SQLite is only allowed in test environment. "
            "Use PostgreSQL for development and production."
        )

    if not settings.admin_key and settings.app_env != "test":
        raise ValueError(
            "ADMIN_KEY is required for admin authentication. "
            "Set it to a secure random string."
        )
