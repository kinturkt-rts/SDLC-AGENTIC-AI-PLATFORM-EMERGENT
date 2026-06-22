"""SearchEvent ORM model."""
from __future__ import annotations

from sqlalchemy import Integer, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class SearchEvent(Base):
    __tablename__ = "search_events"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: __import__('uuid').uuid4().__str__(), server_default=func.gen_random_uuid())
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_article_ids: Mapped[list | None] = mapped_column(JSON().with_variant(JSON(), "sqlite"), nullable=True, default=list)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[object] = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
