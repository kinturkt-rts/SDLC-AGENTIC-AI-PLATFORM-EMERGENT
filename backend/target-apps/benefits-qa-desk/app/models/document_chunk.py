"""DocumentChunk ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import pg_uuid_column


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()), server_default=func.gen_random_uuid()
    )
    document_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    # embedding stored as Text in SQLite; vector(1024) in Postgres via DDL
    embedding: Mapped[str | None] = mapped_column(String, nullable=True)

    document = relationship("Document", back_populates="chunks", lazy="select")
