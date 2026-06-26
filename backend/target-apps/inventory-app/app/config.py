"""Service configuration loaded from environment.

FR-12: app must fail to start with a clear error if `DATABASE_URL` or
`JWT_SECRET_KEY` are missing. Validation is performed in `validate_required()`
which `app.main` calls during the FastAPI lifespan startup hook.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────
    app_env: str = Field("development", alias="APP_ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    service_name: str = Field("inventory-desk", alias="SERVICE_NAME")
    port: int = Field(8000, alias="PORT")

    # ── Postgres (RDS) ───────────────────────────────────────────────────
    database_url: str = Field("", alias="DATABASE_URL")
    postgres_schema: str = Field("inventory_app", alias="POSTGRES_SCHEMA")

    # ── Auth (JWT) ───────────────────────────────────────────────────────
    jwt_secret_key: str = Field("", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(60, alias="JWT_EXPIRE_MINUTES")

    # ── CORS ─────────────────────────────────────────────────────────────
    cors_origins: list[str] = Field(default_factory=list, alias="CORS_ORIGINS")

    def validate_required(self) -> None:
        """Raise RuntimeError when env vars required for runtime are missing.

        Tests bypass this by injecting their own settings/database; production
        startup calls this from the FastAPI lifespan to honour FR-12.
        """
        missing: list[str] = []
        if not self.database_url:
            missing.append("DATABASE_URL")
        if not self.jwt_secret_key:
            missing.append("JWT_SECRET_KEY")
        if missing:
            raise RuntimeError(
                "Missing required environment variables: "
                + ", ".join(missing)
                + ". Copy .env.example to .env and populate them."
            )


settings = Settings()
