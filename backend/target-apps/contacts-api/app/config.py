"""Application configuration via pydantic-settings."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    service_name: str = "contacts-api"
    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(default="", alias="DATABASE_URL")
    postgres_schema: str = Field(default="contacts_api", alias="POSTGRES_SCHEMA")
    api_key: str = Field(default="", alias="API_KEY")
    port: int = Field(default=8000, alias="PORT")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()