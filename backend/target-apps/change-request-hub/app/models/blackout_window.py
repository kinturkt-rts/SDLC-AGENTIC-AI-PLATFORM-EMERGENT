"""BlackoutWindow ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class BlackoutWindow(Base):
    __tablename__ = "blackout_windows"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()), server_default=func.gen_random_uuid())
    environment_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("environments.id"), nullable=False)
    start_at = mapped_column(TimestampTZ, nullable=False)
    end_at = mapped_column(TimestampTZ, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    created_by: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("users.id"), nullable=False)
    created_at = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
