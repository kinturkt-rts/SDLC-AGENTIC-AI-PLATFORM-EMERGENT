"""Application configuration — pydantic-settings.

All env vars read from .env or OS environment. Never set defaults to
real secrets or sqlite:// when design mandates Postgres.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Central configuration — one source of truth for env vars."""

    # App
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    service_name: str = Field(default="student-management", alias="SERVICE_NAME")
    port: int = Field(default=8000, alias="PORT")

    # Database
    database_url: str = Field(default="", alias="DATABASE_URL")
    postgres_schema: str = Field(default="student_management", alias="POSTGRES_SCHEMA")

    # Auth — two-tier API keys
    write_api_key: str = Field(default="", alias="WRITE_API_KEY")
    read_api_key: str = Field(default="", alias="READ_API_KEY")

    # CORS
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
