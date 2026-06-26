from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "library-catalog"
    
    # Database
    database_url: str = Field(default="", alias="DATABASE_URL")
    postgres_schema: str = Field(default="library_catalog", alias="POSTGRES_SCHEMA")
    
    # Authentication
    api_key: str = Field(default="", alias="API_KEY")
    librarian_token: str = Field(default="", alias="LIBRARIAN_TOKEN")
    
    # Business logic
    loan_days: int = Field(default=14, alias="LOAN_DAYS")
    max_active_loans: int = Field(default=5, alias="MAX_ACTIVE_LOANS")
    
    # App environment
    app_env: Literal["development", "test", "production"] = Field(default="development", alias="APP_ENV")
    skip_startup_checks: bool = Field(default=False, alias="SKIP_STARTUP_CHECKS")


@lru_cache
def get_settings() -> Settings:
    return Settings()