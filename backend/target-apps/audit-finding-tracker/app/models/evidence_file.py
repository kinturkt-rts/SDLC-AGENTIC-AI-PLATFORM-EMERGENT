"""Evidence file model for S3 metadata tracking."""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class EvidenceFile(Base):
    """Evidence file metadata storage."""
    
    __tablename__ = "evidence_files"
    
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
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(
        pg_uuid_column(),
        ForeignKey("users.id"),
        nullable=False
    )
    uploaded_at: Mapped[TimestampTZ] = mapped_column(
        TimestampTZ,
        nullable=False,
        server_default=func.now()
    )
    
    # Relationships
    finding = relationship("Finding", foreign_keys=[finding_id], back_populates="evidence_files")
    uploader = relationship("User", foreign_keys=[uploaded_by], back_populates="uploaded_evidence")
    
    def __repr__(self) -> str:
        return f"<EvidenceFile(id={self.id}, filename={self.filename}, finding_id={self.finding_id})>"