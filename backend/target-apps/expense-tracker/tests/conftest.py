"""Test configuration — expense-tracker.

Sets up SQLite in-memory, patches UUID types, overrides auth for tests.
"""
from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import date, datetime, timezone
from decimal import Decimal
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


# ── 1. Environment BEFORE any app import ──
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "expense_tracker")
os.environ.setdefault("API_KEY", "test-admin-key")


# ── 3. UUID TypeDecorator for SQLite ──
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


# ── 4. Now import app (AFTER env is set) ──
from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
import app.models  # noqa: E402, F401
from app.dependencies import CurrentUser, get_current_user  # noqa: E402


# ── 5. Engine + session fixtures ──
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

    fastapi_app.dependency_overrides[get_db] = _override
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


# ── 6. Auth override helpers ──
ADMIN_ID = "b1b2c3d4-0001-4000-8000-000000000001"
MANAGER_ID = "b1b2c3d4-0003-4000-8000-000000000003"
EMPLOYEE_ID = "b1b2c3d4-0004-4000-8000-000000000004"
TEAM_ID = "a1b2c3d4-0001-4000-8000-000000000001"


def _make_user(role: str, user_id: str | None = None, team_id: str | None = None, email: str | None = None) -> CurrentUser:
    return CurrentUser(
        user_id=user_id or str(uuid.uuid4()),
        email=email or f"{role}@example.com",
        role=role,
        team_id=team_id,
    )


@pytest.fixture()
def admin_user() -> CurrentUser:
    return _make_user("admin", user_id=ADMIN_ID)


@pytest.fixture()
def manager_user() -> CurrentUser:
    return _make_user("manager", user_id=MANAGER_ID, team_id=TEAM_ID)


@pytest.fixture()
def employee_user() -> CurrentUser:
    return _make_user("employee", user_id=EMPLOYEE_ID, team_id=TEAM_ID, email="alice@example.com")


@pytest.fixture()
def auth_as_admin(admin_user: CurrentUser):
    """Override auth to impersonate admin."""
    fastapi_app.dependency_overrides[get_current_user] = lambda: admin_user
    yield
    fastapi_app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def auth_as_manager(manager_user: CurrentUser):
    """Override auth to impersonate manager."""
    fastapi_app.dependency_overrides[get_current_user] = lambda: manager_user
    yield
    fastapi_app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def auth_as_employee(employee_user: CurrentUser):
    """Override auth to impersonate employee."""
    fastapi_app.dependency_overrides[get_current_user] = lambda: employee_user
    yield
    fastapi_app.dependency_overrides.pop(get_current_user, None)


# ── 7. Seed data fixtures ──

@pytest.fixture()
def seed_team(db_session: Session) -> str:
    """Insert a test team and return its id."""
    from app.models.team import Team
    team = Team(id=TEAM_ID, name="Engineering", description="Engineering team")
    db_session.add(team)
    db_session.commit()
    return TEAM_ID


@pytest.fixture()
def seed_user(db_session: Session, seed_team: str) -> str:
    """Insert a test employee user and return id."""
    from app.models.user import User
    user = User(
        id=EMPLOYEE_ID,
        email="alice@example.com",
        role="employee",
        team_id=seed_team,
        token_hash="$2b$04$fakehash",
    )
    db_session.add(user)
    db_session.commit()
    return EMPLOYEE_ID


@pytest.fixture()
def seed_fx(db_session: Session) -> None:
    """Insert FX snapshots for testing."""
    from app.models.fx_snapshot import FxSnapshot
    snapshots = [
        FxSnapshot(id=str(uuid.uuid4()), currency="USD", date=date(2024, 6, 1), rate_to_usd=Decimal("1.0000")),
        FxSnapshot(id=str(uuid.uuid4()), currency="GBP", date=date(2024, 6, 1), rate_to_usd=Decimal("1.2700")),
        FxSnapshot(id=str(uuid.uuid4()), currency="EUR", date=date(2024, 6, 1), rate_to_usd=Decimal("1.0900")),
        FxSnapshot(id=str(uuid.uuid4()), currency="USD", date=date(2024, 6, 15), rate_to_usd=Decimal("1.0000")),
    ]
    db_session.add_all(snapshots)
    db_session.commit()


@pytest.fixture()
def seed_expense(db_session: Session, seed_team: str, seed_user: str, seed_fx: None) -> str:
    """Insert a submitted expense and audit log entry, return expense id."""
    from app.models.expense import Expense
    from app.models.audit_log import AuditLog

    expense_id = "e1b2c3d4-0001-4000-8000-000000000001"

    # Insert expense first and flush to satisfy FK
    expense = Expense(
        id=expense_id,
        user_id=seed_user,
        team_id=seed_team,
        amount=Decimal("100.0000"),
        currency="GBP",
        amount_usd=Decimal("127.0000"),
        category="travel",
        description="Train ticket",
        expense_date=date(2024, 6, 1),
        status="submitted",
    )
    db_session.add(expense)
    db_session.flush()  # Ensure expense row exists before audit_log FK

    # Insert audit log entry (mirrors route side-effect)
    audit = AuditLog(
        id=str(uuid.uuid4()),
        expense_id=expense_id,
        actor_id=seed_user,
        actor_role="employee",
        action="created",
        from_status=None,
        to_status="submitted",
        metadata_json={"amount": "100.0000", "currency": "GBP"},
    )
    db_session.add(audit)
    db_session.commit()
    return expense_id
