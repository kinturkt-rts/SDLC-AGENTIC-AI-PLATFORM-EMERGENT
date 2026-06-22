"""Postgres column type helpers."""

from __future__ import annotations

from sqlalchemy import DateTime, Enum as SAEnum, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.config import get_settings

TimestampTZ = DateTime(timezone=True)


def pg_schema() -> str:
    return get_settings().postgres_schema or "public"


def pg_enum(name: str, *values: str) -> SAEnum:
    enum_type = SAEnum(
        *values,
        name=name,
        schema=pg_schema(),
        create_type=False,
        native_enum=True,
        validate_strings=True,
    )
    return enum_type.with_variant(String(32), "sqlite")


def pg_uuid_column():
    return PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")
