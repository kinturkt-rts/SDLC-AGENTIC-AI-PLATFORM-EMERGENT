"""Team ORM model."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    created_at = mapped_column(TimestampTZ, nullable=True, default=lambda: datetime.now(timezone.utc))
    deleted_at = mapped_column(TimestampTZ, nullable=True)
