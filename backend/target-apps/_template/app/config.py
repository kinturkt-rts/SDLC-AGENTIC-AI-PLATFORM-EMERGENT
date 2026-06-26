"""Service configuration — loaded from environment / .env at startup.

ADAPT checklist:
  - Change service_name default to your app name.
  - Add Field lines for app-specific env vars (e.g. BEDROCK_MODEL_ID for B+).
  - Remove Field lines for features not used (e.g. RAG fields for non-RAG apps).
  - Keep all Field(alias="ENV_VAR") patterns — pydantic-settings needs them.
  - NEVER set database_url default to sqlite:// — leave empty and let startup_checks catch it.
"""
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
        """Local dev: app .env wins over inherited IDE/shell sqlite stubs from pipeline/pytest."""
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return (init_settings, env_settings, dotenv_settings, file_secret_settings)
        skip = os.environ.get("SKIP_STARTUP_CHECKS", "").strip().lower()
        if skip in ("1", "true", "yes"):
            return (init_settings, env_settings, dotenv_settings, file_secret_settings)
        return (init_settings, dotenv_settings, env_settings, file_secret_settings)

    # ── App ──────────────────────────────────────────────────────────────
    app_env: str = Field("development", alias="APP_ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    service_name: str = Field("service-template", alias="SERVICE_NAME")  # ADAPT

    # ── Postgres (RDS) ───────────────────────────────────────────────────
    database_url: str = Field("", alias="DATABASE_URL")
    postgres_schema: str = Field("public", alias="POSTGRES_SCHEMA")

    # ── Auth ─────────────────────────────────────────────────────────────
    api_key: str = Field("", alias="API_KEY")
    # Uncomment for JWT auth:
    # jwt_secret_key: str = Field("", alias="JWT_SECRET_KEY")
    # jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    # jwt_expire_minutes: int = Field(60, alias="JWT_EXPIRE_MINUTES")

    # ── CORS ─────────────────────────────────────────────────────────────
    cors_origins: list[str] = Field(default_factory=lambda: ["*"], alias="CORS_ORIGINS")

    # ── AWS / Bedrock — uncomment for B+ / B++ patterns ──────────────────
    aws_region: str = Field("us-east-2", alias="AWS_REGION")
    # bedrock_model_id: str = Field("", alias="BEDROCK_MODEL_ID")
    # bedrock_max_tokens: int = Field(4096, alias="BEDROCK_MAX_TOKENS")

    # ── RAG / pgvector — uncomment for B++ pattern ───────────────────────
    # bedrock_embed_model_id: str = Field("", alias="BEDROCK_EMBED_MODEL_ID")
    # embed_dim: int = Field(1024, alias="EMBED_DIM")
    # chunk_size: int = Field(1000, alias="CHUNK_SIZE")
    # chunk_overlap: int = Field(150, alias="CHUNK_OVERLAP")
    # retrieval_top_k: int = Field(5, alias="RETRIEVAL_TOP_K")
    # confidence_threshold: float = Field(0.25, alias="CONFIDENCE_THRESHOLD")
    # pdf_storage_dir: str = Field("./var/pdfs", alias="PDF_STORAGE_DIR")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
