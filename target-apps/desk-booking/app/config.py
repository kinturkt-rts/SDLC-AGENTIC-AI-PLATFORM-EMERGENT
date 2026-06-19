"""Service configuration — loaded from environment / .env at startup."""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────
    app_env: str = Field("development", alias="APP_ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    service_name: str = Field("desk-booking", alias="SERVICE_NAME")
    skip_startup_checks: bool = Field(False, alias="SKIP_STARTUP_CHECKS")

    # ── Postgres (RDS) ───────────────────────────────────────────────────
    database_url: str = Field("", alias="DATABASE_URL")
    postgres_schema: str = Field("desk_booking", alias="POSTGRES_SCHEMA")

    # ── Auth ─────────────────────────────────────────────────────────────
    admin_key: str = Field("", alias="ADMIN_KEY")

    # ── AWS (platform) ───────────────────────────────────────────────────
    aws_region: str = Field("us-east-2", alias="AWS_REGION")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
