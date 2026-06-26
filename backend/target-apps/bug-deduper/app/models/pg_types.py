"""PostgreSQL type helpers for RDS parity with SQLite test fallback."""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from pgvector.sqlalchemy import Vector


def pg_uuid_column():
    """UUID column that works on both Postgres and SQLite."""
    return PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")


def pg_uuid_pk():
    """UUID PK with defaults for both Postgres and Python (SQLite)."""
    return pg_uuid_column()


class BugStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"
    closed = "closed"
    duplicate = "duplicate"


class KeyTier(str, enum.Enum):
    standard = "standard"
    admin = "admin"


def bug_status_column():
    return SAEnum(
        BugStatus,
        name="bug_status",
        schema="bug_deduper",
        create_type=False,
        native_enum=True,
    ).with_variant(String(20), "sqlite")


def key_tier_column():
    return SAEnum(
        KeyTier,
        name="key_tier",
        schema="bug_deduper",
        create_type=False,
        native_enum=True,
    ).with_variant(String(20), "sqlite")


def embedding_column():
    """pgvector column sized to match Bedrock model (see Settings.embedding_dimension)."""
    from app.config import get_settings

    dim = get_settings().embedding_dimension
    return Vector(dim).with_variant(Text, "sqlite")
