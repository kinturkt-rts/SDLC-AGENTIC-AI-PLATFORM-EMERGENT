"""Test configuration and fixtures."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "bug_deduper")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("ADMIN_KEY", "test-admin-key")
os.environ.setdefault("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
os.environ.setdefault("DEDUP_TOP_K", "3")
os.environ.setdefault("DEDUP_THRESHOLD", "0.85")


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


from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.bug import Bug, BugStatus  # noqa: E402
from app.services.dedup_service import DedupService, SimilarBug, get_dedup_service  # noqa: E402


def _build_test_engine() -> Engine:
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
def mock_dedup() -> MagicMock:
    fake = MagicMock(spec=DedupService)
    fake.embed_description.return_value = [1.0, 0.0, 0.0]
    fake.find_similar.return_value = []
    fake.store_embedding.return_value = None
    return fake


@pytest.fixture()
def client(
    engine: Engine, db_session: Session, mock_dedup: MagicMock
) -> Generator[TestClient, None, None]:
    _db_module.engine = engine
    _db_module.SessionLocal.configure(bind=engine)

    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override_db():
        sess = TestingSession()
        try:
            yield sess
        finally:
            sess.close()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_dedup_service] = lambda: mock_dedup
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def api_headers() -> dict[str, str]:
    return {"X-API-Key": os.environ["API_KEY"]}


@pytest.fixture()
def admin_headers() -> dict[str, str]:
    return {
        "X-API-Key": os.environ["API_KEY"],
        "X-Admin-Key": os.environ["ADMIN_KEY"],
    }


@pytest.fixture()
def seeded_open_bug(db_session: Session) -> Bug:
    bug = Bug(
        id=str(uuid.uuid4()),
        title="Login fails on Safari",
        description="Users cannot log in when using Safari on iOS 17.",
        status=BugStatus.OPEN,
    )
    db_session.add(bug)
    db_session.commit()
    db_session.refresh(bug)
    return bug


@pytest.fixture()
def seeded_closed_bug(db_session: Session) -> Bug:
    bug = Bug(
        id=str(uuid.uuid4()),
        title="Old Safari login issue",
        description="Safari login broken on iOS 16.",
        status=BugStatus.CLOSED,
    )
    db_session.add(bug)
    db_session.commit()
    db_session.refresh(bug)
    return bug


def make_similar(bug: Bug, score: float) -> SimilarBug:
    return SimilarBug(
        id=bug.id,
        title=bug.title,
        description=bug.description,
        score=score,
    )
