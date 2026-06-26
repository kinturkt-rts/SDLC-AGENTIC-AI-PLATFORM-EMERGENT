"""PinnedArticle ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import pg_uuid_column


class PinnedArticle(Base):
    __tablename__ = "pinned_articles"
    __table_args__ = (
        UniqueConstraint("category_id", "article_id", name="uq_pinned_category_article"),
    )

    id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    category_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("categories.id"), nullable=False
    )
    article_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("articles.id"), nullable=False
    )
    pinned_by: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("users.id"), nullable=False
    )
    pinned_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)

    article = relationship("Article", lazy="joined")
