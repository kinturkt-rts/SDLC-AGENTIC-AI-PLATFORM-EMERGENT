"""Bug ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import BugStatus, bug_status_column, embedding_column, pg_uuid_pk


class Bug(Base):
    __tablename__ = "bugs"

    id: Mapped[str] = mapped_column(
        pg_uuid_pk(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = Column("embedding", embedding_column(), nullable=True)
    status: Mapped[str] = mapped_column(
        bug_status_column(),
        nullable=False,
        default=BugStatus.open.value,
        server_default="open",
    )
    duplicate_of: Mapped[str | None] = mapped_column(
        pg_uuid_pk(),
        ForeignKey("bugs.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )
