"""Finding model with status workflow and optimistic locking."""

from __future__ import annotations

import uuid
from typing import Optional
from datetime import date

from sqlalchemy import ForeignKey, String, Text, Integer, Date, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_enum, pg_uuid_column


class Finding(Base):
    """Core finding with workflow state management and optimistic locking."""
    
    __tablename__ = "findings"
    
    id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid()
    )
    audit_id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        ForeignKey("audits.id"),
        nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(
        pg_enum("finding_severity", "low", "medium", "high", "critical"),
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        pg_enum("finding_status", "draft", "assigned", "in_progress", "pending_verification", "verified", "closed"),
        nullable=False,
        default="draft"
    )
    assigned_to: Mapped[Optional[str]] = mapped_column(pg_uuid_column(), ForeignKey("users.id"))
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    created_by: Mapped[str] = mapped_column(
        pg_uuid_column(),
        ForeignKey("users.id"),
        nullable=False
    )
    created_at: Mapped[TimestampTZ] = mapped_column(
        TimestampTZ,
        nullable=False,
        server_default=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # Relationships
    audit = relationship("Audit", foreign_keys=[audit_id], back_populates="findings")
    assignee = relationship("User", foreign_keys=[assigned_to], back_populates="assigned_findings")
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_findings")
    evidence_files = relationship("EvidenceFile", back_populates="finding", cascade="all, delete-orphan")
    status_history = relationship("StatusHistory", back_populates="finding", cascade="all, delete-orphan")
    comments = relationship("FindingComment", back_populates="finding", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Finding(id={self.id}, title={self.title}, status={self.status}, severity={self.severity})>"