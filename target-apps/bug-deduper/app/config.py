from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration for the bug deduplicator service."""

    service_name: str = "bug-deduper"
    app_env: str = Field(default="development", alias="APP_ENV")

    database_url: str = Field(default="", alias="DATABASE_URL")
    postgres_schema: str = Field(default="bug_deduper", alias="POSTGRES_SCHEMA")

    api_key: str = Field(default="", alias="API_KEY")
    admin_key: str = Field(default="", alias="ADMIN_KEY")

    aws_profile: str = Field(default="", alias="AWS_PROFILE")
    aws_region: str = Field(default="us-east-2", alias="AWS_REGION")
    aws_access_key_id: str = Field(default="", alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="", alias="AWS_SECRET_ACCESS_KEY")
    aws_session_token: str = Field(default="", alias="AWS_SESSION_TOKEN")
    bedrock_region: str = Field(default="us-east-2", alias="BEDROCK_REGION")
    bedrock_embed_model_id: str = Field(
        default="amazon.titan-embed-text-v2:0", alias="BEDROCK_EMBED_MODEL_ID"
    )

    dedup_top_k: int = Field(default=3, alias="DEDUP_TOP_K")
    dedup_threshold: float = Field(default=0.85, alias="DEDUP_THRESHOLD")
    max_title_length: int = Field(default=500, alias="MAX_TITLE_LENGTH")

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
