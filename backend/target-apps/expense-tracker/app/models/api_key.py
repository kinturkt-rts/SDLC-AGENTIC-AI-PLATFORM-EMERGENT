"""ApiKey ORM model — stores hashed API keys for manager and admin auth."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key_hash: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    owner_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    team_ids: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at = mapped_column(TimestampTZ, nullable=True, default=lambda: datetime.now(timezone.utc))
    revoked_at = mapped_column(TimestampTZ, nullable=True)
