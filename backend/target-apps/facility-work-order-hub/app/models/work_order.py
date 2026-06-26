"""WorkOrder ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_enum, pg_uuid_column

wo_category = pg_enum("wo_category_enum", "HVAC", "plumbing", "electrical", "access", "general")
wo_priority = pg_enum("wo_priority_enum", "low", "normal", "urgent")
wo_status = pg_enum("wo_status_enum", "submitted", "triaged", "assigned", "in_progress", "completed", "closed")


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(wo_category, nullable=False)
    priority: Mapped[str] = mapped_column(wo_priority, nullable=False)
    status: Mapped[str] = mapped_column(wo_status, nullable=False, default="submitted")
    requester_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("users.id"), nullable=False)
    assignee_id: Mapped[str | None] = mapped_column(pg_uuid_column(), ForeignKey("users.id"), nullable=True)
    site_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("sites.id"), nullable=False)
    location_id: Mapped[str | None] = mapped_column(pg_uuid_column(), ForeignKey("locations.id"), nullable=True)
    due_by: Mapped[str | None] = mapped_column(TimestampTZ, nullable=True)
    reopen_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(TimestampTZ, server_default=func.now(), nullable=False)
    updated_at: Mapped[str] = mapped_column(TimestampTZ, server_default=func.now(), onupdate=func.now(), nullable=False)
    assigned_at: Mapped[str | None] = mapped_column(TimestampTZ, nullable=True)
    started_at: Mapped[str | None] = mapped_column(TimestampTZ, nullable=True)
    completed_at: Mapped[str | None] = mapped_column(TimestampTZ, nullable=True)
    closed_at: Mapped[str | None] = mapped_column(TimestampTZ, nullable=True)
