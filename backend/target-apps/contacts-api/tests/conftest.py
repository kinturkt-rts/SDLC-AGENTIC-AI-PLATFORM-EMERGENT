"""Conftest for contacts-api test suite.

This handles:
  1. Env-before-import pattern (DATABASE_URL, POSTGRES_SCHEMA, auth secrets)
  2. bcrypt >= 4.0 / passlib 1.7.x compatibility shim
  3. PG_UUID(as_uuid=True) → SQLite TypeDecorator patching
  4. Schema-qualified table attachment for SQLite
  5. Session-scoped engine + function-scoped rollback sessions
  6. TestClient with dependency override
  7. API-key auth fixtures
"""
from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

# ── 1. Environment BEFORE any app import ─────────────────────────────────────
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "contacts_api")  # actual schema
os.environ.setdefault("API_KEY", "test-key")

# ── 2. UUID TypeDecorator for SQLite ─────────────────────────────────────────
class _UUIDStr(TypeDecorator):
    """Stores UUID as 36-char string in SQLite; round-trips to uuid.UUID."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        # Return str (not uuid.UUID) so Pydantic + JSON encoding stay consistent
        # with PG_UUID(as_uuid=False) used in the real Postgres columns.
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

# ── 3. Now import app (AFTER env is set + shims applied) ────────────────────
from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

# ── 4. Engine + session fixtures ────────────────────────────────────────────

def _build_test_engine() -> Engine:
    """In-memory SQLite with schema attach and FK support."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    schema = os.environ.get("POSTGRES_SCHEMA", "public")

    @event.listens_for(eng, "connect")
    def _on_connect(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        if schema and schema != "public":
            try:
                cur.execute(f"ATTACH DATABASE ':memory:' AS {schema}")
            except Exception:
                pass  # already attached
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

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── 5. Auth fixtures ─────────────────────────────────────────────────────────

@pytest.fixture()
def api_headers():
    """Headers for API-key auth."""
    return {"X-API-Key": os.environ["API_KEY"]}


# ── 6. Seed fixtures ─────────────────────────────────────────────────────────

@pytest.fixture()
def seeded_dept(db_session: Session):
    """Create a test department for testing contacts."""
    from app.models.department import Department
    
    dept = Department(
        id="11111111-1111-1111-1111-111111111111",
        name="Engineering",
        code="ENG"
    )
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)
    return dept


@pytest.fixture()
def seeded_contact(db_session: Session, seeded_dept):
    """Create a test contact."""
    from app.models.contact import Contact
    
    contact = Contact(
        id="22222222-2222-2222-2222-222222222222",
        department_id=seeded_dept.id,
        full_name="John Doe",
        email="john.doe@company.com",
        phone="555-1234",
        title="Software Engineer"
    )
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)
    return contact