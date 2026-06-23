"""Category model for team notice board."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column

if TYPE_CHECKING:
    from app.models.notice import Notice


class Category(Base):
    """Category for organizing team notices."""

    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TimestampTZ,
        nullable=False,
        server_default=func.now(),
    )

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "length(name) >= 1 AND length(name) <= 60",
            name="categories_name_length",
        ),
        CheckConstraint(
            "description IS NULL OR length(description) <= 240",
            name="categories_description_length",
        ),
    )

    notices: Mapped[list["Notice"]] = relationship(back_populates="category")