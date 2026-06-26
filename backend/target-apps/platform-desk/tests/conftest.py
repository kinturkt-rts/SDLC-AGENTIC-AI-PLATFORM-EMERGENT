"""Test configuration for Platform Desk."""
from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
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


# -- 1. Environment BEFORE any app import --
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "platform_desk")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("CONFIDENCE_THRESHOLD", "0.45")
os.environ.setdefault("CHROMA_PERSIST_DIR", "./test_chroma")
os.environ.setdefault("EMBEDDING_MODEL", "all-MiniLM-L6-v2")


# -- 3. UUID TypeDecorator for SQLite --
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


# -- 4. Now import app (AFTER env is set) --
from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


# -- 5. Engine + session fixtures --
def _build_test_engine() -> Engine:
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
                pass
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


# -- 6. Auth fixtures --
@pytest.fixture()
def api_headers():
    """Headers for API-key auth."""
    return {"X-API-Key": os.environ["API_KEY"]}


# -- 7. Seed fixtures --
@pytest.fixture()
def sample_service(db_session: Session):
    from app.models.service import Service
    svc = Service(
        id=str(uuid.uuid4()),
        name="test-payments-api",
        owning_team="Test Team",
        criticality_tier=1,
        active_support=True,
        created_at=_ts("2024-01-01T00:00:00+00:00"),
    )
    db_session.add(svc)
    db_session.commit()
    db_session.refresh(svc)
    return svc


@pytest.fixture()
def sample_runbook(db_session: Session, sample_service):
    from app.models.runbook import Runbook
    rb = Runbook(
        id=str(uuid.uuid4()),
        title="Test Redis Recovery",
        service_id=sample_service.id,
        default_severity="high",
        short_summary="Test runbook",
        author="test-author",
        lifecycle_status="draft",
        created_at=_ts("2024-02-01T00:00:00+00:00"),
        updated_at=_ts("2024-02-01T00:00:00+00:00"),
    )
    db_session.add(rb)
    db_session.commit()
    db_session.refresh(rb)
    return rb


@pytest.fixture()
def sample_step(db_session: Session, sample_runbook):
    from app.models.runbook_step import RunbookStep
    step = RunbookStep(
        id=str(uuid.uuid4()),
        runbook_id=sample_runbook.id,
        step_number=1,
        title="Step 1 - Verify",
        body_text="Check the alert source and verify the issue.",
        estimated_minutes=3,
        warning_callout=None,
    )
    db_session.add(step)
    db_session.commit()
    db_session.refresh(step)
    return step


@pytest.fixture()
def active_runbook(db_session: Session, sample_service):
    from app.models.runbook import Runbook
    from app.models.runbook_step import RunbookStep
    rb = Runbook(
        id=str(uuid.uuid4()),
        title="Active Test Runbook",
        service_id=sample_service.id,
        default_severity="high",
        short_summary="Active runbook for testing",
        author="test-author",
        lifecycle_status="active",
        created_at=_ts("2024-02-01T00:00:00+00:00"),
        updated_at=_ts("2024-02-01T00:00:00+00:00"),
    )
    db_session.add(rb)
    db_session.commit()
    db_session.refresh(rb)
    step = RunbookStep(
        id=str(uuid.uuid4()),
        runbook_id=rb.id,
        step_number=1,
        title="Active Step",
        body_text="Active step body text for testing.",
        estimated_minutes=5,
    )
    db_session.add(step)
    db_session.commit()
    return rb
