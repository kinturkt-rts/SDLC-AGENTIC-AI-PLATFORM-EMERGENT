"""Finding comment model for threaded discussions."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class FindingComment(Base):
    """Threaded discussion support for findings."""
    
    __tablename__ = "finding_comments"
    
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
    author_id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        ForeignKey("users.id"),
        nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[TimestampTZ] = mapped_column(
        TimestampTZ,
        nullable=False,
        server_default=func.now()
    )
    parent_id: Mapped[Optional[str]] = mapped_column(pg_uuid_column(), ForeignKey("finding_comments.id"))
    
    # Relationships
    finding = relationship("Finding", foreign_keys=[finding_id], back_populates="comments")
    author = relationship("User", foreign_keys=[author_id], back_populates="authored_comments")
    parent = relationship("FindingComment", remote_side=[id], backref="replies")
    
    def __repr__(self) -> str:
        return f"<FindingComment(id={self.id}, finding_id={self.finding_id}, author_id={self.author_id})>"