"""Bug ORM model."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Enum as SAEnum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_schema, pg_uuid_column


class BugStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    DUPLICATE = "duplicate"


def _bug_status_column():
    return (
        SAEnum(
            BugStatus,
            name="bug_status_enum",
            schema=pg_schema(),
            create_type=False,
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
        .with_variant(String(32), "sqlite")
    )


class Bug(Base):
    __tablename__ = "bugs"

    id: Mapped[str] = mapped_column(pg_uuid_column(), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[BugStatus] = mapped_column(
        _bug_status_column(),
        nullable=False,
        default=BugStatus.OPEN,
    )
    duplicate_of_id: Mapped[str | None] = mapped_column(
        pg_uuid_column(),
        ForeignKey("bugs.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TimestampTZ, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TimestampTZ, server_default=func.now(), onupdate=func.now(), nullable=False
    )
