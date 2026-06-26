"""Runbook model — mirrors platform_desk.runbooks."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class Runbook(Base):
    __tablename__ = "runbooks"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    service_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("services.id"), nullable=False,
    )
    default_severity: Mapped[str] = mapped_column(String, nullable=False)
    short_summary: Mapped[str | None] = mapped_column(String, nullable=True)
    author: Mapped[str] = mapped_column(String, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(
        String, nullable=False, default="draft",
    )
    created_at: Mapped[datetime] = mapped_column(
        TimestampTZ, nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TimestampTZ, nullable=False, server_default=func.now(), onupdate=func.now(),
    )

    # Relationships
    service = relationship("Service", lazy="joined")
    steps = relationship("RunbookStep", back_populates="runbook", cascade="all, delete-orphan", order_by="RunbookStep.step_number")
