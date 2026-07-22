"""Application configuration via pydantic-settings.

Exports only `get_settings()` factory — never a module-level instance.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # App
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    service_name: str = Field(default="contacts-api", alias="SERVICE_NAME")
    port: int = Field(default=8000, alias="PORT")

    # Database
    database_url: str = Field(default="", alias="DATABASE_URL")
    postgres_schema: str = Field(default="contacts_api", alias="POSTGRES_SCHEMA")

    # Auth
    api_key: str = Field(default="", alias="API_KEY")

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
