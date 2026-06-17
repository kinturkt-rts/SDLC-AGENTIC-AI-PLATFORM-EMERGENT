"""Postgres column type helpers — mirror database-agent DDL in ORM models.

Use when `db/sql/` defines native ENUM or uuid columns. SQLite tests use
``.with_variant(String, "sqlite")`` so pytest does not require Postgres types.
"""
from __future__ import annotations

from sqlalchemy import Enum as SAEnum, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.config import settings


def pg_schema() -> str:
    """Postgres schema from POSTGRES_SCHEMA (database-agent sets per app)."""
    return settings.postgres_schema or "public"


def pg_enum(name: str, *values: str) -> SAEnum:
    """Reference an existing schema-qualified Postgres ENUM (create_type=False)."""
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
    """uuid PK/FK — returns str on both Postgres (as_uuid=False) and SQLite tests."""
    return PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")
