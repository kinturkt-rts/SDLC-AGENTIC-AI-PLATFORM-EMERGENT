"""IncidentTouch model — mirrors platform_desk.incident_touches."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class IncidentTouch(Base):
    __tablename__ = "incident_touches"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    runbook_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("runbooks.id"), nullable=False,
    )
    step_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ticket_reference: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TimestampTZ, nullable=False, server_default=func.now(),
    )
