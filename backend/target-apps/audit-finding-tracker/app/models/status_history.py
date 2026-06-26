"""Status history model for immutable audit trail."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_enum, pg_uuid_column


class StatusHistory(Base):
    """Immutable audit trail for finding status transitions."""
    
    __tablename__ = "status_history"
    
    id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid()
    )
    finding_id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        ForeignKey("findings.id"),
        nullable=False
    )
    from_status: Mapped[Optional[str]] = mapped_column(
        pg_enum("finding_status", "draft", "assigned", "in_progress", "pending_verification", "verified", "closed")
    )
    to_status: Mapped[str] = mapped_column(
        pg_enum("finding_status", "draft", "assigned", "in_progress", "pending_verification", "verified", "closed"),
        nullable=False
    )
    changed_by: Mapped[str] = mapped_column(
        pg_uuid_column(),
        ForeignKey("users.id"),
        nullable=False
    )
    changed_at: Mapped[TimestampTZ] = mapped_column(
        TimestampTZ,
        nullable=False,
        server_default=func.now()
    )
    comment: Mapped[Optional[str]] = mapped_column(Text)
    
    # Relationships
    finding = relationship("Finding", foreign_keys=[finding_id], back_populates="status_history")
    changed_by_user = relationship("User", foreign_keys=[changed_by], back_populates="status_changes")
    
    def __repr__(self) -> str:
        return f"<StatusHistory(id={self.id}, finding_id={self.finding_id}, {self.from_status}->{self.to_status})>"