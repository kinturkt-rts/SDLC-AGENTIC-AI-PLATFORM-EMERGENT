"""SQLAlchemy engine and session factory for Postgres.

Mirrors `target-apps/_template/app/database.py`: synchronous engine, scoped
session per request, and a `connect` event hook that sets `search_path`
to the inventory_app schema (per database-agent HANDOFF.md).

Tests override `get_db` and the engine via `tests/conftest.py`.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


def _is_postgres_url(url: str) -> bool:
    if not url or url.startswith("sqlite"):
        return False
    scheme = url.split(":", 1)[0].lower()
    return scheme.startswith("postgres")


def _make_metadata() -> MetaData:
    """Apply POSTGRES_SCHEMA via MetaData so ForeignKey('other.id') resolves on RDS."""
    url = (settings.database_url or "").strip()
    if _is_postgres_url(url):
        return MetaData(schema=settings.postgres_schema or "inventory_app")
    return MetaData()


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""

    metadata = _make_metadata()


def _postgres_connect_args() -> dict:
    """Set search_path at connect time (reliable with psycopg3 + SQLAlchemy pool)."""
    url = (settings.database_url or "").strip()
    if not _is_postgres_url(url):
        return {}
    schema = settings.postgres_schema or "inventory_app"
    return {"options": f"-c search_path={schema},public"}


def _make_engine() -> Engine:
    url = (settings.database_url or "").strip()
    if not url:
        return create_engine(
            "postgresql+psycopg://placeholder:placeholder@localhost:5432/placeholder",
            pool_pre_ping=False,
        )
    kwargs: dict = {
        "echo": settings.app_env == "development",
        "future": True,
    }
    if _is_postgres_url(url):
        kwargs.update(
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            connect_args=_postgres_connect_args(),
        )
    return create_engine(url, **kwargs)


def verify_db_schema(engine: Engine) -> None:
    """Fail fast at startup when Postgres schema/tables are missing (FR-12)."""
    if engine.dialect.name != "postgresql":
        return
    schema = settings.postgres_schema or "inventory_app"
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT to_regclass(%s)",
            (f"{schema}.users",),
        ).scalar()
    if row is None:
        raise RuntimeError(
            f"Database schema not ready: table {schema}.users not found. "
            "Run: python scripts/apply_sql_to_rds.py --target-app inventory-app "
            "(from repo root). Check DATABASE_URL and POSTGRES_SCHEMA in .env."
        )


engine: Engine = _make_engine()


@event.listens_for(engine, "connect")
def _set_search_path(dbapi_conn, _connection_record) -> None:  # type: ignore[no-untyped-def]
    """Set per-connection search_path so unqualified names resolve to inventory_app."""
    # Skip for non-Postgres dialects (e.g. SQLite test fallback).
    if engine.dialect.name != "postgresql":
        return
    schema = settings.postgres_schema or "inventory_app"
    with dbapi_conn.cursor() as cur:
        cur.execute(f"SET search_path TO {schema}, public")


SessionLocal: sessionmaker[Session] = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yield a request-scoped session, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
