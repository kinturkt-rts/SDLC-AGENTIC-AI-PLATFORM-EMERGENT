"""ArticleEmbedding ORM model."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import pg_uuid_column


class ArticleEmbedding(Base):
    __tablename__ = "article_embeddings"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: __import__('uuid').uuid4().__str__(), server_default=func.gen_random_uuid())
    article_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("articles.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    # embedding vector(384) — stored as text in SQLite, vector in PG
    # For app we skip the column type definition here for SQLite compatibility
    # In tests we store JSON text; in prod pgvector handles it
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    embedded_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=func.now())
