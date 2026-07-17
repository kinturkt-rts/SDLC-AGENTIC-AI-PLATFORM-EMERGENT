"""Application configuration — all env vars declared here.

Import only `get_settings` — never `settings` at module level.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Core ──────────────────────────────────────────────────────────────────
    app_env: str = Field(default="production", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    service_name: str = Field(default="team-faq-bot", alias="SERVICE_NAME")
    port: int = Field(default=8000, alias="PORT")

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(default="", alias="DATABASE_URL")
    postgres_schema: str = Field(default="team_faq_bot", alias="POSTGRES_SCHEMA")

    # ── Auth (API-key) ────────────────────────────────────────────────────────
    api_key: str = Field(default="", alias="API_KEY")
    admin_api_key: str = Field(default="", alias="ADMIN_API_KEY")

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")

    # ── AWS / Bedrock ─────────────────────────────────────────────────────────
    aws_region: str = Field(default="us-east-2", alias="AWS_REGION")
    bedrock_model_id: str = Field(default="anthropic.claude-3-haiku-20240307-v1:0", alias="BEDROCK_MODEL_ID")
    bedrock_max_tokens: int = Field(default=1024, alias="BEDROCK_MAX_TOKENS")
    bedrock_embed_model_id: str = Field(default="amazon.titan-embed-text-v2:0", alias="BEDROCK_EMBED_MODEL_ID")

    # ── RAG / Retrieval ───────────────────────────────────────────────────────
    embed_dim: int = Field(default=1024, alias="EMBED_DIM")
    chunk_size: int = Field(default=500, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=50, alias="CHUNK_OVERLAP")
    retrieval_top_k: int = Field(default=5, alias="RETRIEVAL_TOP_K")
    confidence_threshold: float = Field(default=0.75, alias="CONFIDENCE_THRESHOLD")

    # ── FAQ-specific ──────────────────────────────────────────────────────────
    faq_max_chars: int = Field(default=50000, alias="FAQ_MAX_CHARS")
    retention_days: int = Field(default=90, alias="RETENTION_DAYS")

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
