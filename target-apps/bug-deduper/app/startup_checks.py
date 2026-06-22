"""Fail-fast runtime validation."""

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


def should_skip_startup_checks(settings: Settings) -> bool:
    if os.environ.get("SKIP_STARTUP_CHECKS", "").strip().lower() in ("1", "true", "yes"):
        return True
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    return (settings.app_env or "").strip().lower() == "test"


def validate_runtime_config(settings: Settings) -> None:
    if should_skip_startup_checks(settings):
        return

    url = (settings.database_url or "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and add your RDS DSN."
        )

    if not _is_postgres_url(url):
        raise RuntimeError(
            f"DATABASE_URL must use Postgres for bug-deduper, but got: {url[:60]}..."
        )

    if not settings.api_key:
        raise RuntimeError("API_KEY is not set in .env")

    if not settings.admin_key:
        raise RuntimeError("ADMIN_KEY is not set in .env")

    if not settings.bedrock_embed_model_id:
        raise RuntimeError("BEDROCK_EMBED_MODEL_ID is not set in .env")
