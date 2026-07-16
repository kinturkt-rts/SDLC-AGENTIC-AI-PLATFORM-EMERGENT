"""Test configuration — expense-tracker.

SQLite in-memory with schema ATTACH for expense_tracker schema.
Auth: Bearer token for employees; X-Api-Key for managers/admins.
Tokens are SHA-256 hashed and stored in employees/api_keys tables.
"""
from __future__ import annotations

import hashlib
import os
from collections.abc import Generator
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator


# ── 1. Environment BEFORE any app import ───────────────────────────────
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "expense_tracker")
os.environ.setdefault("AWS_REGION", "us-east-2")


# ── 3. UUID TypeDecorator for SQLite ───────────────────────────────────
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


# ── 4. Now import app (AFTER env is set) ──────────────────────────────
from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
import app.models  # noqa: E402, F401


# ── 5. Engine + session fixtures ──────────────────────────────────────
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


# ── 6. Seed helpers ──────────────────────────────────────────────────
def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@pytest.fixture()
def seed_data(db_session: Session) -> dict:
    """Seed teams, employees, api_keys, and FX rates for test scenarios."""
    from app.models.team import Team
    from app.models.employee import Employee
    from app.models.api_key import ApiKey
    from app.models.fx_rate_snapshot import FxRateSnapshot

    team1 = Team(id=1, name="Engineering")
    team2 = Team(id=2, name="Finance")
    db_session.add_all([team1, team2])
    db_session.flush()

    emp_token = "emp-token-alice"
    emp2_token = "emp-token-bob"
    emp1 = Employee(id=1, name="Alice Johnson", team_id=1, token_hash=_sha256(emp_token), role="employee")
    emp2 = Employee(id=2, name="Bob Smith", team_id=1, token_hash=_sha256(emp2_token), role="employee")
    db_session.add_all([emp1, emp2])
    db_session.flush()

    mgr_key = "mgr-api-key-123"
    mgr = ApiKey(id=1, key_hash=_sha256(mgr_key), role="manager", owner_label="Manager Eng", team_ids="1")
    db_session.add(mgr)

    admin_key = "admin-api-key-456"
    adm = ApiKey(id=2, key_hash=_sha256(admin_key), role="admin", owner_label="Admin Global", team_ids="1,2")
    db_session.add(adm)
    db_session.flush()

    fx1 = FxRateSnapshot(currency="EUR", rate_date=date(2024, 6, 15), usd_rate=Decimal("1.080000"))
    fx2 = FxRateSnapshot(currency="GBP", rate_date=date(2024, 6, 15), usd_rate=Decimal("1.265000"))
    fx3 = FxRateSnapshot(currency="CAD", rate_date=date(2024, 6, 15), usd_rate=Decimal("0.730000"))
    db_session.add_all([fx1, fx2, fx3])
    db_session.commit()

    return {
        "emp_token": emp_token,
        "emp2_token": emp2_token,
        "mgr_key": mgr_key,
        "admin_key": admin_key,
        "team1_id": 1,
        "team2_id": 2,
        "emp1_id": 1,
        "emp2_id": 2,
    }


@pytest.fixture()
def emp_headers(seed_data: dict) -> dict:
    return {"Authorization": f"Bearer {seed_data['emp_token']}"}


@pytest.fixture()
def admin_headers(seed_data: dict) -> dict:
    return {"X-Api-Key": seed_data["admin_key"]}


@pytest.fixture()
def mgr_headers(seed_data: dict) -> dict:
    return {"X-Api-Key": seed_data["mgr_key"]}
