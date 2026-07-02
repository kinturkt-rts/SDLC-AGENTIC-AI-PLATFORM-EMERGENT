"""Test configuration and fixtures."""
import os
import uuid
from datetime import datetime, timezone

# Set env BEFORE any app imports
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "pr_diff_summarizer")
os.environ.setdefault("API_KEY", "test-api-key-12345")
os.environ.setdefault("AWS_REGION", "us-east-2")
os.environ.setdefault("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
os.environ.setdefault("MAX_DIFF_BYTES", "102400")

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine, event, String
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator
from fastapi.testclient import TestClient
from typing import Any

SCHEMA_NAME = "pr_diff_summarizer"


# ── UUID TypeDecorator for SQLite ─────────────────────────────────────────
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


# ── Import app AFTER env is set ───────────────────────────────────────────
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
import app.database as _db_module  # noqa: E402


# ── Engine + session fixtures ─────────────────────────────────────────────
_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    future=True,
)


@event.listens_for(_test_engine, "connect")
def _on_connect(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    try:
        cur.execute(f"ATTACH DATABASE ':memory:' AS \"{SCHEMA_NAME}\"")
    except Exception:
        pass  # already attached
    cur.close()


# Patch UUID columns before creating tables
_patch_uuid_columns_for_sqlite(Base.metadata)
Base.metadata.create_all(bind=_test_engine)

TestSessionLocal = sessionmaker(bind=_test_engine, autoflush=False, autocommit=False)


@pytest.fixture()
def db_session():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Clean up all tables after each test
        with _test_engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.exec_driver_sql(f"DELETE FROM {table.name}")


@pytest.fixture()
def client(db_session):
    _db_module.engine = _test_engine
    _db_module.SessionLocal = TestSessionLocal

    def _override_get_db():
        sess = TestSessionLocal()
        try:
            yield sess
        finally:
            sess.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


@pytest.fixture()
def api_headers():
    return {"X-API-Key": "test-api-key-12345"}


@pytest.fixture()
def mock_bedrock():
    """Mock invoke_summarize at the router import site."""
    fake_result = {
        "summary": "Test summary of the changes.",
        "risk_factors": ["test-factor"],
        "risk_score": 50,
    }
    with patch("app.routers.reviews.invoke_summarize", return_value=fake_result) as mock:
        yield mock


@pytest.fixture()
def mock_bedrock_for_health():
    """Mock get_bedrock_client for health checks."""
    fake_client = MagicMock()
    with patch("app.routers.health.get_bedrock_client", return_value=fake_client):
        yield fake_client


@pytest.fixture()
def sample_review(db_session):
    """Seed a review in the test DB."""
    from app.models.review import Review

    review = Review(
        id=str(uuid.uuid4()),
        title="Test review",
        diff_text="diff --git a/test.py b/test.py\n+hello\n-world",
        file_count=1,
        lines_added=1,
        lines_removed=1,
        summary="A test change.",
        risk_factors=["test"],
        risk_score=25,
        risk_band="low",
        model_id="test-model",
        created_by="test",
        submitted_at=datetime.now(timezone.utc),
    )
    db_session.add(review)
    db_session.commit()
    db_session.refresh(review)
    return review
