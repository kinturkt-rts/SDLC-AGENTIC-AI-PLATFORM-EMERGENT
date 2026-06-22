"""Test configuration for bug-deduper."""
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
os.environ.setdefault("POSTGRES_SCHEMA", "bug_deduper")
os.environ.setdefault("API_KEY_STANDARD", "test-standard-key")
os.environ.setdefault("API_KEY_ADMIN", "test-admin-key")
os.environ.setdefault("AWS_REGION", "us-east-2")
os.environ.setdefault("BEDROCK_REGION", "us-east-2")
os.environ.setdefault("BEDROCK_MODEL_ID", "amazon.titan-embed-text-v2:0")
os.environ.setdefault("EMBEDDING_DIMENSION", "1024")
os.environ.setdefault("SIMILARITY_THRESHOLD", "0.85")
os.environ.setdefault("TOP_K", "3")


# ── 2. UUID TypeDecorator for SQLite ─────────────────────────────────────────
class _UUIDStr(TypeDecorator):
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
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID
    for table in metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, PG_UUID):
                col.type = _UUIDStr()


# ── 3. Now import app (AFTER env is set) ─────────────────────────────────────
from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


# ── 4. Engine + session fixtures ─────────────────────────────────────────────
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


# ── 5. Auth fixtures ─────────────────────────────────────────────────────────
@pytest.fixture()
def standard_headers():
    return {"X-API-Key": os.environ["API_KEY_STANDARD"]}


@pytest.fixture()
def admin_headers():
    return {"X-API-Key": os.environ["API_KEY_ADMIN"]}


# ── 6. Bedrock mock ─────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def mock_bedrock(monkeypatch):
    """Mock Bedrock to avoid live AWS calls in tests."""
    from unittest.mock import MagicMock

    fake = MagicMock()
    fake.embed.return_value = [0.1] * 1024
    fake.ping.return_value = True

    # Patch at the services module level (where health.py imports it lazily from)
    monkeypatch.setattr("app.services.bedrock_client.get_bedrock_client", lambda: fake)
    monkeypatch.setattr("app.routers.bugs.get_bedrock_client", lambda: fake)
    return fake


# ── 7. Seed fixtures ─────────────────────────────────────────────────────────
@pytest.fixture()
def sample_bug(db_session: Session) -> dict:
    """Insert a sample open bug."""
    from app.models.bug import Bug
    bug_id = str(uuid.uuid4())
    bug = Bug(
        id=bug_id,
        title="Sample bug",
        description="Sample description",
        embedding="[" + ",".join(["0.1"] * 1024) + "]",
        status="open",
    )
    db_session.add(bug)
    db_session.commit()
    return {"id": bug_id, "title": "Sample bug", "description": "Sample description"}
