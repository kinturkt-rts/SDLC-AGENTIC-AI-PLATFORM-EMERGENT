"""Reusable Postgres-parity column types for SQLAlchemy models."""
from __future__ import annotations

import uuid

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import mapped_column

# Match TIMESTAMPTZ columns from database-agent DDL on Postgres; SQLite tests use the same type.
TimestampTZ = DateTime(timezone=True)


def pg_uuid_column(**kwargs):
    """UUID column with sqlite parity."""
    return PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")


def pg_uuid_pk():
    """Primary key UUID column with defaults for both Postgres and SQLite."""
    return mapped_column(
        PG_UUID(as_uuid=False).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
