"""Application configuration via pydantic-settings."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "sqlite:///./dev.db"
    postgres_schema: str = "healthcare_clinic_bot"
    port: int = 8000

    # JWT auth
    jwt_secret_key: str = "change-me-local-only"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # AWS Bedrock
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    aws_region: str = "us-east-2"

    # FAQ relevance
    faq_relevance_threshold: float = 0.1


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
