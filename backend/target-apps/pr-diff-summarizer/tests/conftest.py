"""Test configuration and fixtures for PR Diff Summarizer tests."""

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
os.environ.setdefault("POSTGRES_SCHEMA", "pr_diff_summarizer")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("AWS_REGION", "us-east-2")
os.environ.setdefault("BEDROCK_REGION", "us-east-2")
os.environ.setdefault("BEDROCK_MODEL_ID", "test-model")

# ── 2. UUID TypeDecorator for SQLite ─────────────────────────────────────────
class _UUIDStr(TypeDecorator):
    """Stores UUID as 36-char string in SQLite; returns str (not uuid.UUID)."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)  # Return str, not UUID, for JSON serialization


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
    """Headers for API-key auth apps."""
    return {"X-API-Key": os.environ["API_KEY"]}


# ── 6. Mock Bedrock client ───────────────────────────────────────────────────

@pytest.fixture()
def mock_bedrock(monkeypatch):
    """Mock Bedrock client for testing."""
    from unittest.mock import MagicMock
    
    fake = MagicMock()
    fake.invoke_text.return_value = '{"summary": "Test AI summary of diff changes", "risk_score": 45}'
    
    # Patch at the import site where routers use it
    monkeypatch.setattr("app.routers.reviews.get_bedrock_client", lambda: fake)
    return fake


# ── 7. Seed data fixtures ────────────────────────────────────────────────────

@pytest.fixture()
def seeded_review(db_session):
    """Create a sample review for testing."""
    from app.models.review import Review, RiskBandEnum
    
    review_id = str(uuid.uuid4())
    review = Review(
        id=review_id,
        title="Test PR: Add feature",
        diff_text="diff --git a/test.py b/test.py\n+def new_function():\n+    return True",
        file_count=1,
        lines_added=2,
        lines_removed=0,
        summary="Adds a new test function",
        risk_score=25,
        risk_band=RiskBandEnum.LOW,
        model_id="test-model",
        created_by="test-key"
    )
    db_session.add(review)
    db_session.commit()
    db_session.refresh(review)
    return review