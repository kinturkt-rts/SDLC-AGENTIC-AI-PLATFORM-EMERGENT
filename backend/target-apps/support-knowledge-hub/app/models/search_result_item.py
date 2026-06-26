"""SearchResultItem ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import pg_uuid_column


class SearchResultItem(Base):
    __tablename__ = "search_result_items"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    search_log_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("search_logs.id", ondelete="CASCADE"), nullable=False
    )
    article_id: Mapped[str] = mapped_column(
        pg_uuid_column(), ForeignKey("articles.id"), nullable=False
    )
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)
