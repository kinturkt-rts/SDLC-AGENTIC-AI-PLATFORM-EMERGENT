"""Service configuration — loaded from environment / .env at startup."""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return (init_settings, env_settings, dotenv_settings, file_secret_settings)
        skip = os.environ.get("SKIP_STARTUP_CHECKS", "").strip().lower()
        if skip in ("1", "true", "yes"):
            return (init_settings, env_settings, dotenv_settings, file_secret_settings)
        return (init_settings, dotenv_settings, env_settings, file_secret_settings)

    # ── App ──────────────────────────────────────────────────────────────
    app_env: str = Field("development", alias="APP_ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    service_name: str = Field("notice-board-ui", alias="SERVICE_NAME")

    # ── Postgres (RDS) ───────────────────────────────────────────────────
    database_url: str = Field("", alias="DATABASE_URL")
    postgres_schema: str = Field("notice_board_ui", alias="POSTGRES_SCHEMA")

    # ── Auth — organizer shared secret ───────────────────────────────────
    organizer_secret: str = Field("", alias="ORGANIZER_SECRET")

    # ── CORS ─────────────────────────────────────────────────────────────
    cors_origins: list[str] = Field(default_factory=lambda: ["*"], alias="CORS_ORIGINS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
