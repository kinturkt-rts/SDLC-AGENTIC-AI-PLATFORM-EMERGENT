from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration settings for PR Diff Summarizer service."""
    
    service_name: str = "pr-diff-summarizer"
    app_env: str = Field(default="development", alias="APP_ENV")
    
    # Database
    database_url: str = Field(default="", alias="DATABASE_URL")
    postgres_schema: str = Field(default="pr_diff_summarizer", alias="POSTGRES_SCHEMA")
    
    # Authentication
    api_key: str = Field(default="", alias="API_KEY")
    
    # AWS Bedrock — profile (SSO) OR explicit session keys from root .env
    aws_profile: str = Field(default="", alias="AWS_PROFILE")
    aws_region: str = Field(default="us-east-2", alias="AWS_REGION")
    aws_access_key_id: str = Field(default="", alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="", alias="AWS_SECRET_ACCESS_KEY")
    aws_session_token: str = Field(default="", alias="AWS_SESSION_TOKEN")
    bedrock_region: str = Field(default="us-east-2", alias="BEDROCK_REGION")
    bedrock_model_id: str = Field(default="us.anthropic.claude-sonnet-4-20250514-v1:0", alias="BEDROCK_MODEL_ID")
    bedrock_max_tokens: int = Field(default=4096, alias="BEDROCK_MAX_TOKENS")
    
    # Input limits
    max_diff_size_mb: int = Field(default=10, alias="MAX_DIFF_SIZE_MB")
    max_title_length: int = Field(default=500, alias="MAX_TITLE_LENGTH")
    
    # Retry configuration
    bedrock_retry_attempts: int = Field(default=3, alias="BEDROCK_RETRY_ATTEMPTS")
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()