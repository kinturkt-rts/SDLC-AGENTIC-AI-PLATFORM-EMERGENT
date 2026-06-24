"""Test configuration for notice-board-ui.

Adapted from _template/tests/conftest_reference.py.
Schema: notice_board_ui
Auth: organizer shared secret (X-Organizer-Secret header)
"""
from __future__ import annotations

import os
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

# ── 1. Environment BEFORE any app import ─────────────────────────────────────
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "notice_board_ui")
os.environ.setdefault("ORGANIZER_SECRET", "test-organizer-secret")

# ── 2. Now import app (AFTER env is set) ─────────────────────────────────────
from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

SCHEMA_NAME = "notice_board_ui"


# ── 3. Engine helpers ────────────────────────────────────────────────────────
def _build_test_engine() -> Engine:
    """In-memory SQLite with schema attach and FK support."""
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
        try:
            cur.execute(f"ATTACH DATABASE ':memory:' AS {SCHEMA_NAME}")
        except Exception:
            pass  # already attached
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

    app.dependency_overrides[get_db] = _override
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ── 4. Auth fixtures ─────────────────────────────────────────────────────────

@pytest.fixture()
def organizer_headers() -> dict[str, str]:
    """Headers with valid organizer secret."""
    return {"X-Organizer-Secret": os.environ["ORGANIZER_SECRET"]}


@pytest.fixture()
def reader_headers() -> dict[str, str]:
    """Headers for anonymous reader (no auth required)."""
    return {}


# ── 5. Seed fixtures ──────────────────────────────────────────────────────────

@pytest.fixture()
def sample_category(db_session: Session):
    """Insert a category and return it."""
    from app.models.category import Category

    cat = Category(name="General", description="General announcements")
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


@pytest.fixture()
def sample_notice(db_session: Session, sample_category):
    """Insert an active notice and return it."""
    from app.models.notice import Notice

    notice = Notice(
        title="Test Notice",
        body="This is a test notice body.",
        category_id=sample_category.id,
        author_display_name="Test Author",
        archived=False,
    )
    db_session.add(notice)
    db_session.commit()
    db_session.refresh(notice)
    return notice


@pytest.fixture()
def archived_notice(db_session: Session, sample_category):
    """Insert an archived notice and return it."""
    from app.models.notice import Notice

    notice = Notice(
        title="Archived Notice",
        body="This notice is archived.",
        category_id=sample_category.id,
        author_display_name="Test Author",
        archived=True,
    )
    db_session.add(notice)
    db_session.commit()
    db_session.refresh(notice)
    return notice
