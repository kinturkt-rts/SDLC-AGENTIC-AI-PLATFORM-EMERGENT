"""ChangeRequest ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class ChangeRequest(Base):
    __tablename__ = "change_requests"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()), server_default=func.gen_random_uuid())
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    service_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("services.id"), nullable=False)
    target_environment_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("environments.id"), nullable=False)
    change_type: Mapped[str] = mapped_column(String, nullable=False)  # standard|normal|emergency
    risk: Mapped[str] = mapped_column(String, nullable=False)  # low|medium|high|critical
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    requester_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("users.id"), nullable=False)
    implementer_id: Mapped[Optional[str]] = mapped_column(pg_uuid_column(), ForeignKey("users.id"), nullable=True)
    planned_start = mapped_column(TimestampTZ, nullable=False)
    planned_end = mapped_column(TimestampTZ, nullable=False)
    rollback_plan: Mapped[str] = mapped_column(String, nullable=False)
    created_at = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
    updated_at = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
    submitted_at = mapped_column(TimestampTZ, nullable=True)
    approved_at = mapped_column(TimestampTZ, nullable=True)
    scheduled_at = mapped_column(TimestampTZ, nullable=True)
    started_at = mapped_column(TimestampTZ, nullable=True)
    completed_at = mapped_column(TimestampTZ, nullable=True)
    closed_at = mapped_column(TimestampTZ, nullable=True)

    # Relationships for detail view
    approval_records = relationship("ApprovalRecord", backref="change_request", lazy="selectin")
    status_history = relationship("StatusHistory", backref="change_request", lazy="selectin", order_by="StatusHistory.changed_at")
    comments = relationship("Comment", backref="change_request", lazy="selectin", order_by="Comment.posted_at")
