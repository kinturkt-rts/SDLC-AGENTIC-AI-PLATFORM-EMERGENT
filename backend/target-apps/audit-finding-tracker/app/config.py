"""Application configuration using pydantic-settings.

Loads from environment variables with fallback defaults.
Never call Settings() at module level — use get_settings() factory.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """App configuration loaded from environment."""

    service_name: str = "audit-finding-tracker"
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    
    # Database
    database_url: str = Field(default="", alias="DATABASE_URL")
    postgres_schema: str = Field(default="audit_finding_tracker", alias="POSTGRES_SCHEMA")
    
    # JWT Authentication 
    jwt_secret_key: str = Field(default="", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=60, alias="JWT_EXPIRE_MINUTES")
    
    # File Storage (S3 in production, local filesystem for MVP)
    file_storage_type: str = Field(default="local", alias="FILE_STORAGE_TYPE")  # local | s3
    local_upload_dir: str = Field(default="./data/evidence", alias="LOCAL_UPLOAD_DIR")
    max_file_size_mb: int = Field(default=10, alias="MAX_FILE_SIZE_MB")
    
    # S3 Configuration (for production)
    aws_region: str = Field(default="us-east-2", alias="AWS_REGION")
    s3_bucket_name: str = Field(default="", alias="S3_BUCKET_NAME")
    s3_key_prefix: str = Field(default="evidence/", alias="S3_KEY_PREFIX")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance. Use this instead of Settings() everywhere."""
    return Settings()