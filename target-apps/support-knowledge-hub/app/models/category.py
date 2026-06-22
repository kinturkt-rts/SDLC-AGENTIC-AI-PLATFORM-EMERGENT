"""Category ORM model."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: __import__('uuid').uuid4().__str__(), server_default=func.gen_random_uuid())
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_by: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[object] = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
