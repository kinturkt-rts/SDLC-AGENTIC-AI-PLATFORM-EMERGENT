"""StatusHistory ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class StatusHistory(Base):
    __tablename__ = "status_history"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()), server_default=func.gen_random_uuid())
    change_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("change_requests.id"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String, nullable=True)
    to_status: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("users.id"), nullable=False)
    changed_at = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
