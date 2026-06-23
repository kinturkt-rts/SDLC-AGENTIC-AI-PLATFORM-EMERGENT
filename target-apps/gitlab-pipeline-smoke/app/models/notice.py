"""Notice model for team notice board."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column

if TYPE_CHECKING:
    from app.models.category import Category


class Notice(Base):
    """Team notice for announcements and wins."""

    __tablename__ = "notices"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    category_id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        ForeignKey("categories.id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author_name: Mapped[str] = mapped_column(String(80), nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(TimestampTZ, nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(TimestampTZ, nullable=True)
    is_archived: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        TimestampTZ,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TimestampTZ,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "length(title) >= 1 AND length(title) <= 120",
            name="notices_title_length",
        ),
        CheckConstraint(
            "length(body) >= 1 AND length(body) <= 4000",
            name="notices_body_length",
        ),
        CheckConstraint(
            "length(author_name) >= 1 AND length(author_name) <= 80",
            name="notices_author_name_length",
        ),
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at >= starts_at",
            name="notices_ends_after_starts",
        ),
    )

    category: Mapped["Category"] = relationship(back_populates="notices")