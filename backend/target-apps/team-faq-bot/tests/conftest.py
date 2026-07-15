"""Test configuration — SQLite in-memory with schema ATTACH."""
from __future__ import annotations

import os
from collections.abc import Generator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def _ts(iso: str) -> datetime:
    """ISO string → datetime for ORM TimestampTZ columns."""
    return datetime.fromisoformat(iso)


# ── 1. Environment BEFORE any app import ─────────────────────────────────────
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "team_faq_bot")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key")
os.environ.setdefault("AWS_REGION", "us-east-2")
os.environ.setdefault("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
os.environ.setdefault("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
os.environ.setdefault("CONFIDENCE_THRESHOLD", "0.75")
os.environ.setdefault("RETRIEVAL_TOP_K", "5")


# ── 2. Now import app (AFTER env) ───────────────────────────────────────────
from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
import app.models  # noqa: E402, F401


# ── 3. Engine + session fixtures ────────────────────────────────────────────

def _build_test_engine() -> Engine:
    """In-memory SQLite with schema attach."""
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


# ── 4. Auth fixtures ───────────────────────────────────────────────────────

@pytest.fixture()
def api_headers():
    """Headers for user API-key auth."""
    return {"X-API-Key": os.environ["API_KEY"]}


@pytest.fixture()
def admin_headers():
    """Headers for admin API-key auth."""
    return {"X-API-Key": os.environ["ADMIN_API_KEY"]}


# ── 5. Seed data fixtures ───────────────────────────────────────────────────

@pytest.fixture()
def seed_collection(db_session: Session):
    """Seed an active FAQ collection with chunks."""
    from app.models.faq_collection import FaqCollection
    from app.models.faq_chunk import FaqChunk

    coll = FaqCollection(
        filename="test-faq.txt",
        raw_text="Q: How do I request PTO?\nA: Submit in BambooHR.",
        char_count=47,
        uploaded_at=_ts("2024-01-15T09:00:00+00:00"),
        is_active=True,
    )
    db_session.add(coll)
    db_session.flush()

    chunk = FaqChunk(
        collection_id=coll.id,
        heading="PTO Policy",
        chunk_text="Q: How do I request PTO?\nA: Submit in BambooHR.",
        embedding=None,
    )
    db_session.add(chunk)
    db_session.commit()
    return coll


@pytest.fixture()
def seed_question_logs(db_session: Session):
    """Seed question log entries."""
    from app.models.question_log import QuestionLog

    logs = [
        QuestionLog(
            question_text="How do I request PTO?",
            status="answered",
            logged_at=_ts("2024-02-01T10:15:00+00:00"),
            expires_at=_ts("2024-05-01T10:15:00+00:00"),
        ),
        QuestionLog(
            question_text="How do I set up local dev environment?",
            status="not_in_faq",
            logged_at=_ts("2024-02-03T09:00:00+00:00"),
            expires_at=_ts("2024-05-03T09:00:00+00:00"),
        ),
        QuestionLog(
            question_text="Where do I find architecture diagrams?",
            status="not_in_faq",
            logged_at=_ts("2024-02-04T14:20:00+00:00"),
            expires_at=_ts("2024-05-04T14:20:00+00:00"),
        ),
    ]
    db_session.add_all(logs)
    db_session.commit()
    return logs
