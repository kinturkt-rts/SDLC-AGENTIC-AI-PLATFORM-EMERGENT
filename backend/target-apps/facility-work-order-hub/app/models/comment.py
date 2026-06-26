"""Comment ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()))
    work_order_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("work_orders.id"), nullable=False)
    author_id: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(TimestampTZ, server_default=func.now(), nullable=False)
