"""User model for role-based access control."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_enum, pg_uuid_column


class User(Base):
    """User model with Cognito integration and role-based access control."""
    
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid()
    )
    cognito_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        pg_enum("user_role", "auditor", "assignee", "executive"),
        nullable=False
    )
    created_at: Mapped[TimestampTZ] = mapped_column(
        TimestampTZ,
        nullable=False,
        server_default=func.now()
    )
    
    # Relationships
    created_audits = relationship("Audit", foreign_keys="[Audit.created_by]", back_populates="creator")
    assigned_findings = relationship("Finding", foreign_keys="[Finding.assigned_to]", back_populates="assignee")
    created_findings = relationship("Finding", foreign_keys="[Finding.created_by]", back_populates="creator")
    uploaded_evidence = relationship("EvidenceFile", back_populates="uploader")
    status_changes = relationship("StatusHistory", back_populates="changed_by_user")
    authored_comments = relationship("FindingComment", back_populates="author")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"