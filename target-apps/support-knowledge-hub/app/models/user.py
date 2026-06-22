"""User ORM model."""
from __future__ import annotations

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: __import__('uuid').uuid4().__str__(), server_default=func.gen_random_uuid())
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[object] = mapped_column(TimestampTZ, nullable=False, server_default=func.now())
