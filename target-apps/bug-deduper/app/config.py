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
    service_name: str = Field("bug-deduper", alias="SERVICE_NAME")

    # ── Postgres (RDS) ───────────────────────────────────────────────────
    database_url: str = Field("", alias="DATABASE_URL")
    postgres_schema: str = Field("bug_deduper", alias="POSTGRES_SCHEMA")

    # ── Auth (two-tier API key) ──────────────────────────────────────────
    api_key_standard: str = Field("", alias="API_KEY_STANDARD")
    api_key_admin: str = Field("", alias="API_KEY_ADMIN")

    # ── CORS ─────────────────────────────────────────────────────────────
    cors_origins: list[str] = Field(default_factory=lambda: ["*"], alias="CORS_ORIGINS")

    # ── AWS / Bedrock ────────────────────────────────────────────────────
    aws_region: str = Field("us-east-2", alias="AWS_REGION")
    bedrock_region: str = Field("us-east-2", alias="BEDROCK_REGION")
    bedrock_model_id: str = Field("amazon.titan-embed-text-v2:0", alias="BEDROCK_MODEL_ID")
    embedding_dimension: int = Field(0, alias="EMBEDDING_DIMENSION")

    # ── Dedup config ─────────────────────────────────────────────────────
    similarity_threshold: float = Field(0.85, alias="SIMILARITY_THRESHOLD")
    top_k: int = Field(3, alias="TOP_K")

    def model_post_init(self, __context: object) -> None:
        if self.embedding_dimension <= 0:
            self.embedding_dimension = _embedding_dimension_for_model(self.bedrock_model_id)


_MODEL_EMBEDDING_DIMENSIONS: dict[str, int] = {
    "amazon.titan-embed-text-v1": 1536,
    "amazon.titan-embed-text-v2:0": 1024,
}


def _embedding_dimension_for_model(model_id: str) -> int:
    model = (model_id or "").strip()
    for prefix, dim in _MODEL_EMBEDDING_DIMENSIONS.items():
        if model.startswith(prefix) or prefix in model:
            return dim
    return 1536


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
