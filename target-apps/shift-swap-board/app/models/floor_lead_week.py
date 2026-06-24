"""ORM model for floor_lead_weeks table."""
from __future__ import annotations

import uuid

from sqlalchemy import Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import pg_uuid_column


class FloorLeadWeek(Base):
    __tablename__ = "floor_lead_weeks"
    __table_args__ = (
        UniqueConstraint("week_start", name="uq_floor_lead_week_start"),
    )

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    week_start: Mapped[str] = mapped_column(Date, nullable=False)
    floor_lead_user_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("users.id"), nullable=False
    )
