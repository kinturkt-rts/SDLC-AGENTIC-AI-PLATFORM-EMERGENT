"""Audit model for containing multiple findings."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_enum, pg_uuid_column


class Audit(Base):
    """Audit container with lifecycle management."""
    
    __tablename__ = "audits"
    
    id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid()
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        pg_enum("audit_status", "planning", "active", "completed", "archived"),
        nullable=False,
        default="planning"
    )
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
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_audits")
    findings = relationship("Finding", back_populates="audit")
    
    def __repr__(self) -> str:
        return f"<Audit(id={self.id}, title={self.title}, status={self.status})>"