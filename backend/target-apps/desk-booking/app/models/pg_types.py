"""PostgreSQL-specific types with SQLite fallback for tests."""
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


def pg_uuid_column():
    """UUID column that works on Postgres and SQLite."""
    return PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")


def slot_type_enum():
    """slot_type ENUM (full, am, pm) with SQLite fallback."""
    return PG_ENUM(
        "full",
        "am",
        "pm",
        name="slot_type",
        schema="desk_booking",
        create_type=False,
        native_enum=True,
    ).with_variant(String(10), "sqlite")
