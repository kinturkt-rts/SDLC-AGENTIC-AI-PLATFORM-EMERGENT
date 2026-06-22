"""PinnedArticle ORM model."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class PinnedArticle(Base):
    __tablename__ = "pinned_articles"
    __table_args__ = (
        UniqueConstraint("category_id", "article_id", name="uq_pinned_category_article"),
    )

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: __import__('uuid').uuid4().__str__(), server_default=func.gen_random_uuid())
    category_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("categories.id"), nullable=False)
    article_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("articles.id"), nullable=False)
    pinned_by: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("users.id"), nullable=False)
    pinned_at: Mapped[object] = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
