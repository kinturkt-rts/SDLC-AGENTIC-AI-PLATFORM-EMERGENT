"""Reusable SQLAlchemy column types for Postgres / SQLite portability."""
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# UUID column portable across Postgres (native uuid) and SQLite (string 36)
PG_UUID_COL = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")
