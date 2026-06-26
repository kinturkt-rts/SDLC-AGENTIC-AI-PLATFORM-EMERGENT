"""Database engine and session management."""
from __future__ import annotations

import os

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def _build_engine() -> Engine:
    from app.config import get_settings

    settings = get_settings()
    url = settings.database_url

    if not url:
        # Allow import but engine ops will fail
        url = "sqlite:///:memory:"

    if url.startswith("sqlite"):
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
        schema = settings.postgres_schema
        if schema and schema != "public":

            @event.listens_for(engine, "connect")
            def _attach_schema(dbapi_conn, _rec):
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                try:
                    cur.execute(f"ATTACH DATABASE ':memory:' AS {schema}")
                except Exception:
                    pass
                cur.close()
    else:
        engine = create_engine(
            url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        schema = settings.postgres_schema

        @event.listens_for(engine, "connect")
        def _set_search_path(dbapi_conn, _rec):
            with dbapi_conn.cursor() as cur:
                cur.execute(f"SET search_path TO {schema}, public")
                dbapi_conn.commit()

    return engine


# Lazy engine + session
engine: Engine | None = None
SessionLocal: sessionmaker[Session] = sessionmaker(autocommit=False, autoflush=False)


def _get_engine() -> Engine:
    global engine
    if engine is None:
        engine = _build_engine()
        SessionLocal.configure(bind=engine)
    return engine


def get_db():
    """FastAPI dependency — yields a DB session and closes it after."""
    _get_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ping_database() -> bool:
    """Quick connectivity check."""
    try:
        eng = _get_engine()
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
