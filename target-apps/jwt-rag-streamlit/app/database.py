"""SQLAlchemy engine and session factory.

Dialect-aware: SQLite (pytest) skips pool args; Postgres sets search_path.
Tests override the engine via conftest.py — this module's engine/SessionLocal
are the production defaults.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


def _is_postgres_url(url: str) -> bool:
    if not url or url.startswith("sqlite"):
        return False
    return url.split(":", 1)[0].lower().startswith("postgres")


def _make_metadata() -> MetaData:
    settings = get_settings()
    url = (settings.database_url or "").strip()
    if _is_postgres_url(url):
        return MetaData(schema=settings.postgres_schema or "public")
    return MetaData()


class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy models."""

    metadata = _make_metadata()


def _postgres_connect_args() -> dict:
    settings = get_settings()
    url = (settings.database_url or "").strip()
    if not _is_postgres_url(url):
        return {}
    schema = settings.postgres_schema or "public"
    return {"options": f"-c search_path={schema},public"}


def _make_engine() -> Engine:
    settings = get_settings()
    url = (settings.database_url or "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example -> .env and fill in your RDS DSN."
        )
    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            future=True,
        )
    eng = create_engine(
        url,
        echo=settings.app_env == "development",
        future=True,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args=_postgres_connect_args(),
    )

    @event.listens_for(eng, "connect")
    def _set_search_path(dbapi_conn, _connection_record):
        schema = settings.postgres_schema or "public"
        with dbapi_conn.cursor() as cur:
            cur.execute(f'SET search_path TO "{schema}", public')

    return eng


engine: Engine = _make_engine()

SessionLocal: sessionmaker[Session] = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a scoped DB session, always closed on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()