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
    
    # AWS Bedrock
    aws_region: str = Field(default="us-east-2", alias="AWS_REGION")
    bedrock_region: str = Field(default="us-east-2", alias="BEDROCK_REGION")
    bedrock_model_id: str = Field(default="us.anthropic.claude-sonnet-4-20250514-v1:0", alias="BEDROCK_MODEL_ID")
    
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