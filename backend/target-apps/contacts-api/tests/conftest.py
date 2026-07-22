"""Test fixtures for contacts-api.

SQLite in-memory with StaticPool. API-key auth only (no JWT).
"""
from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator


def _ts(iso: str) -> datetime:
    """ISO string -> datetime for ORM TimestampTZ columns in SQLite tests."""
    return datetime.fromisoformat(iso)


# -- 1. Environment BEFORE any app import ---------------------------------
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "contacts_api")
os.environ.setdefault("API_KEY", "test-key")


# -- 3. UUID TypeDecorator for SQLite ----------------------------------------
class _UUIDStr(TypeDecorator):
    """Stores UUID as 36-char string in SQLite; round-trips to str."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)


def _patch_uuid_columns_for_sqlite(metadata: Any) -> None:
    """Replace PG_UUID columns with _UUIDStr so sqlite3 can bind them."""
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID
    for table in metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, PG_UUID):
                col.type = _UUIDStr()


# -- 4. Import app AFTER env is set -------------------------------------------
from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
import app.models  # noqa: E402, F401


# -- 5. Engine + session fixtures --------------------------------------------
def _build_test_engine() -> Engine:
    """In-memory SQLite with StaticPool and FK support."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(eng, "connect")
    def _on_connect(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return eng


@pytest.fixture(scope="session")
def engine() -> Engine:
    eng = _build_test_engine()
    if eng.dialect.name == "sqlite":
        _patch_uuid_columns_for_sqlite(Base.metadata)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def db_session(engine: Engine) -> Generator[Session, None, None]:
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.exec_driver_sql(f"DELETE FROM {table.name}")


@pytest.fixture()
def client(engine: Engine, db_session: Session) -> Generator[TestClient, None, None]:
    _db_module.engine = engine
    _db_module.SessionLocal.configure(bind=engine)

    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override():
        sess = TestingSession()
        try:
            yield sess
        finally:
            sess.close()

    fastapi_app.dependency_overrides[get_db] = _override
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


# -- 6. Auth fixtures (API-key only) ------------------------------------------
@pytest.fixture()
def api_headers():
    """Headers for API-key auth."""
    return {"X-API-Key": os.environ["API_KEY"]}


# -- 7. Seed fixtures ---------------------------------------------------------
@pytest.fixture()
def sample_department(db_session: Session):
    """Create and return a sample department."""
    from app.models.department import Department
    dept = Department(
        id=str(uuid.uuid4()),
        name="Engineering",
        code="ENG",
        created_at=_ts("2024-01-15T09:00:00+00:00"),
    )
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)
    return dept


@pytest.fixture()
def sample_contact(db_session: Session, sample_department):
    """Create and return a sample contact."""
    from app.models.contact import Contact
    contact = Contact(
        id=str(uuid.uuid4()),
        department_id=sample_department.id,
        full_name="Alice Chen",
        email="alice.chen@example.com",
        phone="+1-555-0101",
        title="Senior Backend Engineer",
        is_active=True,
        created_at=_ts("2024-02-01T10:00:00+00:00"),
        updated_at=_ts("2024-02-01T10:00:00+00:00"),
    )
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)
    return contact
