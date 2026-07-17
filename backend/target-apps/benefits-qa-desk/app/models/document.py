"""Document ORM model."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_enum, pg_uuid_column

document_status_enum = pg_enum("document_status", "waiting", "processing", "ready", "failed")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()), server_default=func.gen_random_uuid()
    )
    collection_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("collections.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(document_status_enum, nullable=False, server_default="waiting")
    uploaded_by: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("users.id"), nullable=False)
    uploaded_at: Mapped[Optional[datetime]] = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    collection = relationship("Collection", back_populates="documents", lazy="select")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan", lazy="select")
