"""Article ORM model."""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: __import__('uuid').uuid4().__str__(), server_default=func.gen_random_uuid())
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("categories.id"), nullable=False)
    tags: Mapped[list | None] = mapped_column(JSON().with_variant(JSON(), "sqlite"), nullable=True, default=list)
    author_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_at: Mapped[object] = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
    updated_at: Mapped[object] = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
    published_at: Mapped[object | None] = mapped_column(TimestampTZ, nullable=True)
    archived_at: Mapped[object | None] = mapped_column(TimestampTZ, nullable=True)
