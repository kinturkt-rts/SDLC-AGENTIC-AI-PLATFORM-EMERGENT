"""User ORM model — mirrors `inventory_app.users` (DDL 001)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.schema import orm_table_args


class UserRole(str, enum.Enum):
    """Mirrors Postgres `inventory_app.user_role` enum."""

    admin = "admin"
    staff = "staff"


class User(Base):
    __tablename__ = "users"
    __table_args__ = orm_table_args()

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Stored as the enum string value (`'admin'` / `'staff'`); native PG enum
    # accepts these literals directly, and SQLite stores them as plain text.
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
