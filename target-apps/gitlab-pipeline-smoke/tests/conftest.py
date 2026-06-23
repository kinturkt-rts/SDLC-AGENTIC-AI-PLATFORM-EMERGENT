"""Test configuration for gitlab-pipeline-smoke (Pattern B API-key, SQLite in tests)."""
from __future__ import annotations

import os
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator


def _ts(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _now() -> datetime:
    return datetime.now(timezone.utc)


os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "gitlab_pipeline_smoke")
os.environ.setdefault("API_KEY", "test-key")


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
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = testing_session()
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
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override():
        sess = testing_session()
        try:
            yield sess
        finally:
            sess.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def api_headers() -> dict[str, str]:
    return {"X-API-Key": os.environ["API_KEY"]}


@pytest.fixture()
def seed_categories(db_session: Session) -> dict[str, str]:
    from app.models import Category

    categories = [
        Category(
            id="550e8400-e29b-41d4-a716-446655440000",
            name="General",
            description="General announcements and company-wide notices",
            created_at=_ts("2024-01-01T10:00:00+00:00"),
        ),
        Category(
            id="550e8400-e29b-41d4-a716-446655440001",
            name="HR",
            description="Human resources updates, benefits, and policy changes",
            created_at=_ts("2024-01-01T10:00:00+00:00"),
        ),
        Category(
            id="550e8400-e29b-41d4-a716-446655440002",
            name="Engineering",
            description="Technical updates, deployment notices, and engineering wins",
            created_at=_ts("2024-01-01T10:00:00+00:00"),
        ),
    ]
    for category in categories:
        db_session.add(category)
    db_session.commit()
    return {cat.name.lower(): cat.id for cat in categories}


@pytest.fixture()
def seed_notices(db_session: Session, seed_categories: dict[str, str]) -> dict[str, str]:
    from app.models import Notice

    now = _now()
    notices = [
        Notice(
            id="660e8400-e29b-41d4-a716-446655440000",
            category_id=seed_categories["general"],
            title="Welcome to Q1 2024",
            body="We are starting the new quarter with exciting initiatives.",
            author_name="Alice Johnson",
            starts_at=now - timedelta(days=7),
            ends_at=now + timedelta(days=365),
            is_archived=False,
            created_at=now - timedelta(days=7),
            updated_at=now - timedelta(days=7),
        ),
        Notice(
            id="660e8400-e29b-41d4-a716-446655440001",
            category_id=seed_categories["general"],
            title="Upcoming All-Hands Meeting",
            body="Our quarterly all-hands meeting is scheduled for next month.",
            author_name="David Wilson",
            starts_at=now + timedelta(days=30),
            ends_at=now + timedelta(days=31),
            is_archived=False,
            created_at=now,
            updated_at=now,
        ),
        Notice(
            id="660e8400-e29b-41d4-a716-446655440002",
            category_id=seed_categories["hr"],
            title="Holiday Party RSVP Reminder",
            body="Please RSVP for the holiday party by December 15th.",
            author_name="Eva Martinez",
            starts_at=now - timedelta(days=400),
            ends_at=now - timedelta(days=30),
            is_archived=False,
            created_at=now - timedelta(days=400),
            updated_at=now - timedelta(days=400),
        ),
        Notice(
            id="660e8400-e29b-41d4-a716-446655440003",
            category_id=seed_categories["engineering"],
            title="Legacy System Deprecation",
            body="The old ticketing system has been successfully deprecated.",
            author_name="Frank Brown",
            starts_at=now - timedelta(days=200),
            ends_at=now + timedelta(days=30),
            is_archived=True,
            created_at=now - timedelta(days=200),
            updated_at=now - timedelta(days=15),
        ),
    ]
    for notice in notices:
        db_session.add(notice)
    db_session.commit()
    return {notice.title.lower().replace(" ", "_"): notice.id for notice in notices}
