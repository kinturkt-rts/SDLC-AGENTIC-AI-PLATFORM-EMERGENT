"""Test configuration — environment setup, fixtures, DB override."""
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
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "healthcare_clinic_bot")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-for-prod")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")
os.environ.setdefault("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
os.environ.setdefault("AWS_REGION", "us-east-2")
os.environ.setdefault("FAQ_RELEVANCE_THRESHOLD", "0.1")

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
    pass  # bcrypt not installed standalone — use app's default


# ── 3. UUID TypeDecorator for SQLite ─────────────────────────────────────────
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


# ── 4. Now import app (AFTER env is set + shims applied) ────────────────────
from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


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
        # Clean tables between tests
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


# ── 6. Auth fixtures ────────────────────────────────────────────────────────

@pytest.fixture()
def staff_user(db_session: Session) -> dict:
    """Seed a staff user and return info including token."""
    from app.models.user import User
    from app.security import create_access_token, hash_password

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        username="teststaff",
        hashed_password=hash_password("TestPass123!"),
        role="staff",
    )
    db_session.add(user)
    db_session.commit()
    token = create_access_token(subject=user_id, role="staff")
    return {"id": user_id, "username": "teststaff", "token": token}


@pytest.fixture()
def staff_headers(staff_user: dict) -> dict:
    """Authorization headers for staff user."""
    return {"Authorization": f"Bearer {staff_user['token']}"}
