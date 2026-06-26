"""Pytest configuration and shared fixtures for this service.

Place service-level fixtures here. Database override, TestClient, and
auth helpers are wired so tests never hit real RDS or external APIs.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Set before any `from app.*` import so Settings() and engine use test DB.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("POSTGRES_SCHEMA", "app_schema")
os.environ.setdefault("API_KEY", "test-key")

# ── In-memory SQLite for unit / integration tests ────────────────────────────
TEST_DATABASE_URL = os.environ["DATABASE_URL"]

_test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(_test_engine, "connect")
def _attach_postgres_schema(dbapi_conn, _record):
    """Mirror schema-qualified Postgres tables when POSTGRES_SCHEMA is not public."""
    schema = os.environ.get("POSTGRES_SCHEMA", "public")
    if schema and schema != "public":
        cur = dbapi_conn.cursor()
        try:
            cur.execute(f"ATTACH DATABASE ':memory:' AS {schema}")
        finally:
            cur.close()
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


@pytest.fixture(scope="session")
def db_engine():
    """Session-scoped engine — create tables once per test run."""
    from app.database import Base  # noqa: PLC0415

    Base.metadata.create_all(bind=_test_engine)
    yield _test_engine
    _test_engine.dispose()


@pytest.fixture()
def db_session(db_engine) -> Generator[Session, None, None]:
    """Function-scoped DB session; rolls back after each test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient with DB session override — no real RDS connection needed."""
    from app.database import get_db  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
