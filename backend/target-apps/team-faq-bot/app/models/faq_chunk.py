"""ORM model for faq_chunks table."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FaqChunk(Base):
    __tablename__ = "faq_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(Integer, ForeignKey("faq_collection.id"), nullable=False)
    heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Embedding stored as TEXT in SQLite tests; vector(1024) on Postgres
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
