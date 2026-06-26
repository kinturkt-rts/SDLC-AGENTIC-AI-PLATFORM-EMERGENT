"""ArticleChunk ORM model (vector embeddings for semantic search)."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import pg_uuid_column


class ArticleChunk(Base):
    __tablename__ = "article_chunks"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    article_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(String, nullable=False)
    # embedding stored as text in SQLite tests, as vector(1024) in Postgres
    embedding: Mapped[str | None] = mapped_column(String, nullable=True)
