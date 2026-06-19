"""PostgreSQL / SQLite compatible type helpers."""
from __future__ import annotations

import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# UUID column compatible with both Postgres (native uuid) and SQLite (string 36)
PG_UUID_COL = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")


def generate_uuid() -> str:
    return str(uuid.uuid4())
