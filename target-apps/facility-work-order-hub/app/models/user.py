"""User ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_enum, pg_uuid_column

user_role = pg_enum("user_role_enum", "requester", "technician", "facilities_admin", "leadership")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(user_role, nullable=False)
    created_at: Mapped[str] = mapped_column(TimestampTZ, server_default=func.now(), nullable=False)
