"""Test configuration — env setup before imports, SQLite fixtures."""
from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import date, datetime
from typing import Any

import pytest
from sqlalchemy import Date, DateTime, String, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

# ── 1. Environment BEFORE any app import ─────────────────────────────────────
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "it_asset_lifecycle")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-not-for-prod")
os.environ.setdefault("JWT_TTL_HOURS", "8")
os.environ.setdefault("ASSET_ENCRYPTION_KEY", "VGVzdEtleTEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNA==")
os.environ.setdefault("AWS_REGION", "us-east-2")

# Generate a proper Fernet key for tests
from cryptography.fernet import Fernet
_test_fernet_key = Fernet.generate_key().decode("utf-8")
os.environ["ASSET_ENCRYPTION_KEY"] = _test_fernet_key

# ── 2. bcrypt compatibility shim ─────────────────────────────────────────────
import app.security as _security_mod  # noqa: E402

try:
    import bcrypt as _bcrypt_lib

    def _compat_hash(plain: str) -> str:
        return _bcrypt_lib.hashpw(
            plain.encode("utf-8"), _bcrypt_lib.gensalt(rounds=4)
        ).decode("utf-8")

    def _compat_verify(plain: str, hashed: str) -> bool:
        try:
            return _bcrypt_lib.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False

    _security_mod.hash_password = _compat_hash
    _security_mod.verify_password = _compat_verify
except ImportError:
    pass


# ── 3. UUID TypeDecorator for SQLite ─────────────────────────────────────────
class _UUIDStr(TypeDecorator):
    """Stores UUID as 36-char string in SQLite."""
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


class _SQLiteDate(TypeDecorator):
    """Accept ISO date strings in tests (SQLite Date requires date objects)."""
    impl = Date
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> date | None:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value)
        raise TypeError(f"Expected date or ISO string, got {type(value)!r}")


def _patch_date_columns_for_sqlite(metadata: Any) -> None:
    for table in metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, Date):
                col.type = _SQLiteDate()


class _SQLiteDateTime(TypeDecorator):
    """Accept ISO datetime strings in tests."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        raise TypeError(f"Expected datetime or ISO string, got {type(value)!r}")


def _patch_datetime_columns_for_sqlite(metadata: Any) -> None:
    for table in metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, DateTime):
                col.type = _SQLiteDateTime()


# ── 4. Now import app (AFTER env is set) ────────────────────────────────────
from fastapi.testclient import TestClient  # noqa: E402

from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.security import create_access_token, hash_password  # noqa: E402


# ── 5. Engine + session fixtures ────────────────────────────────────────────

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
                cur.execute(f"ATTACH DATABASE ':memory:' AS \"{schema}\"")
            except Exception:
                pass
        cur.close()

    return eng


@pytest.fixture(scope="session")
def engine() -> Engine:
    eng = _build_test_engine()
    if eng.dialect.name == "sqlite":
        _patch_uuid_columns_for_sqlite(Base.metadata)
        _patch_date_columns_for_sqlite(Base.metadata)
        _patch_datetime_columns_for_sqlite(Base.metadata)
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


# ── 6. Auth + seed fixtures ─────────────────────────────────────────────────

@pytest.fixture()
def seeded_users(db_session: Session) -> dict:
    """Seed users with known credentials; return tokens and IDs."""
    from app.models.user import User

    admin_id = str(uuid.uuid4())
    staff_id = str(uuid.uuid4())
    finance_id = str(uuid.uuid4())

    admin = User(id=admin_id, username="test_admin", password_hash=hash_password("Admin123!"), role="it_admin", is_active=True)
    staff = User(id=staff_id, username="test_staff", password_hash=hash_password("Staff123!"), role="it_staff", is_active=True)
    finance = User(id=finance_id, username="test_finance", password_hash=hash_password("Finance123!"), role="finance_readonly", is_active=True)

    db_session.add_all([admin, staff, finance])
    db_session.commit()

    admin_token = create_access_token(subject=admin_id, role="it_admin")
    staff_token = create_access_token(subject=staff_id, role="it_staff")
    finance_token = create_access_token(subject=finance_id, role="finance_readonly")

    return {
        "admin_id": admin_id,
        "staff_id": staff_id,
        "finance_id": finance_id,
        "admin_token": admin_token,
        "staff_token": staff_token,
        "finance_token": finance_token,
    }


@pytest.fixture()
def admin_headers(seeded_users: dict) -> dict:
    return {"Authorization": f"Bearer {seeded_users['admin_token']}"}


@pytest.fixture()
def staff_headers(seeded_users: dict) -> dict:
    return {"Authorization": f"Bearer {seeded_users['staff_token']}"}


@pytest.fixture()
def finance_headers(seeded_users: dict) -> dict:
    return {"Authorization": f"Bearer {seeded_users['finance_token']}"}
