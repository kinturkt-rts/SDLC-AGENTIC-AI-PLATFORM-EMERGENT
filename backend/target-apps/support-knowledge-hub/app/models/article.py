"""Article ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY

from app.database import Base
from app.models.pg_types import pg_uuid_column


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(String, nullable=False)
    category_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("categories.id"), nullable=False
    )
    tags: Mapped[list | None] = mapped_column(JSON().with_variant(JSON(), "sqlite"), nullable=True)
    author_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("users.id"), nullable=False
    )
    state: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    category = relationship("Category", lazy="joined")
    author = relationship("User", lazy="joined")
