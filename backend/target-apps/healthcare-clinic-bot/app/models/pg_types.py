"""Reusable PostgreSQL type helpers for SQLAlchemy models."""
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# UUID column type — stores as native UUID on Postgres, String(36) on SQLite
pg_uuid = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")
