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

    # ── App ──────────────────────────────────────────────────
    app_env: str = Field("development", alias="APP_ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    service_name: str = Field("platform-desk", alias="SERVICE_NAME")

    # ── Postgres (RDS) ─────────────────────────────────────────
    database_url: str = Field("", alias="DATABASE_URL")
    postgres_schema: str = Field("platform_desk", alias="POSTGRES_SCHEMA")

    # ── Auth (API Key) ────────────────────────────────────────
    api_key: str = Field("", alias="API_KEY")

    # ── Vector search ─────────────────────────────────────────
    confidence_threshold: float = Field(0.45, alias="CONFIDENCE_THRESHOLD")
    chroma_persist_dir: str = Field("./chroma_data", alias="CHROMA_PERSIST_DIR")
    embedding_model: str = Field("all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")

    # ── CORS ─────────────────────────────────────────────────
    cors_origins: list[str] = Field(default_factory=lambda: ["*"], alias="CORS_ORIGINS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
