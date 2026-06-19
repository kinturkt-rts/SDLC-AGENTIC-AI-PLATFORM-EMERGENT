"""Test configuration — env-before-import pattern, SQLite engine, auth fixtures."""
from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

# ── 1. Environment BEFORE any app import ─────────────────────────────────
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "desk_booking")
os.environ.setdefault("ADMIN_KEY", "test-admin-key-123")
os.environ.setdefault("AWS_REGION", "us-east-2")


# ── 2. UUID TypeDecorator for SQLite ─────────────────────────────────
class _UUIDStr(TypeDecorator):
    """Stores UUID as string in SQLite; round-trips to str."""
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


# ── 3. Now import app (AFTER env is set) ─────────────────────────────
from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


# ── 4. Engine + session fixtures ────────────────────────────────────
def _build_test_engine() -> Engine:
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    schema = os.environ.get("POSTGRES_SCHEMA", "desk_booking")

    @event.listens_for(eng, "connect")
    def _on_connect(dbapi_conn, _rec):
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
        # Clean all tables after each test
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(text(f"DELETE FROM {table.fullname}"))


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


# ── 5. Seed fixtures ──────────────────────────────────────────────
@pytest.fixture()
def sample_zone(db_session: Session):
    from app.models.zone import Zone
    zone = Zone(id="11111111-1111-1111-1111-111111111001", name="north")
    db_session.add(zone)
    db_session.commit()
    db_session.refresh(zone)
    return zone


@pytest.fixture()
def sample_zones(db_session: Session):
    from app.models.zone import Zone
    north = Zone(id="11111111-1111-1111-1111-111111111001", name="north")
    south = Zone(id="11111111-1111-1111-1111-111111111002", name="south")
    lab = Zone(id="11111111-1111-1111-1111-111111111003", name="lab")
    db_session.add_all([north, south, lab])
    db_session.commit()
    return {"north": north, "south": south, "lab": lab}


@pytest.fixture()
def sample_desk(db_session: Session, sample_zone):
    from app.models.desk import Desk
    desk = Desk(
        id="22222222-2222-2222-2222-222222222001",
        zone_id=sample_zone.id,
        label="N-01",
        is_active=True,
    )
    db_session.add(desk)
    db_session.commit()
    db_session.refresh(desk)
    return desk


@pytest.fixture()
def sample_user(db_session: Session):
    from app.models.user import User
    user = User(
        id="33333333-3333-3333-3333-333333333001",
        email="alice.chen@company.com",
        full_name="Alice Chen",
        user_token="token_alice_stable_001",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def second_user(db_session: Session):
    from app.models.user import User
    user = User(
        id="33333333-3333-3333-3333-333333333002",
        email="bob.smith@company.com",
        full_name="Bob Smith",
        user_token="token_bob_stable_002",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def auth_headers(sample_user):
    return {"X-User-Token": sample_user.user_token}


@pytest.fixture()
def admin_headers():
    return {"X-Admin-Key": os.environ["ADMIN_KEY"]}
