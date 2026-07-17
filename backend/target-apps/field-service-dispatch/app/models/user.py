"""User ORM model — auth + RBAC."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pg_types import pg_uuid_column


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    username: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # dispatcher / technician / owner
    technician_id: Mapped[str | None] = mapped_column(
        pg_uuid_column(), ForeignKey("technicians.id"), nullable=True
    )
    # API key for auth — stored per-user; looked up on each request
    api_key: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)

    technician = relationship("Technician", foreign_keys=[technician_id])
