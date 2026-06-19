"""Test configuration and fixtures for audit-finding-tracker.

This handles env-before-import, bcrypt compatibility, UUID/SQLite patches,
session management, and JWT auth fixtures.
"""
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
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "audit_finding_tracker")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-for-prod")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")
os.environ.setdefault("LOCAL_UPLOAD_DIR", "./test_uploads")

# ── 2. bcrypt / passlib compatibility shim ───────────────────────────────────
_SECURITY_MODULE = None
try:
    import app.security as _security_mod  # noqa: E402
    _SECURITY_MODULE = _security_mod
except ImportError:
    pass  # no security module yet

if _SECURITY_MODULE is not None:
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

        if hasattr(_SECURITY_MODULE, "hash_password"):
            _SECURITY_MODULE.hash_password = _compat_hash
        if hasattr(_SECURITY_MODULE, "verify_password"):
            _SECURITY_MODULE.verify_password = _compat_verify
    except ImportError:
        pass

# ── 3. UUID TypeDecorator for SQLite ─────────────────────────────────────────
class _UUIDStr(TypeDecorator):
    """Stores UUID as 36-char string in SQLite; returns str for consistency."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)  # Return str, not UUID object


def _patch_uuid_columns_for_sqlite(metadata: Any) -> None:
    """Replace PG_UUID columns with _UUIDStr so sqlite3 can bind them."""
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
    """In-memory SQLite with schema attach and FK support."""
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
                pass  # already attached
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

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── 6. App-specific seed fixtures ───────────────────────────────────────────

@pytest.fixture()
def seeded_users(db_session: Session) -> dict[str, Any]:
    """Create test users and return user data with tokens."""
    from app.models.user import User
    from app.security import create_access_token, hash_password
    
    # Test user IDs from seed data
    auditor_id = "550e8400-e29b-41d4-a716-446655440001"
    assignee_id = "550e8400-e29b-41d4-a716-446655440002"  
    executive_id = "550e8400-e29b-41d4-a716-446655440003"
    
    users = [
        User(
            id=auditor_id,
            cognito_sub="test-auditor",
            email="test.auditor@company.com",
            role="auditor"
        ),
        User(
            id=assignee_id,
            cognito_sub="test-assignee",
            email="test.assignee@company.com",
            role="assignee"
        ),
        User(
            id=executive_id,
            cognito_sub="test-executive", 
            email="test.executive@company.com",
            role="executive"
        )
    ]
    
    for user in users:
        db_session.add(user)
    db_session.commit()
    
    # Generate JWT tokens for each role
    auditor_token, _ = create_access_token(subject=auditor_id, role="auditor")
    assignee_token, _ = create_access_token(subject=assignee_id, role="assignee")
    executive_token, _ = create_access_token(subject=executive_id, role="executive")
    
    return {
        "auditor": {"id": auditor_id, "token": auditor_token, "email": "test.auditor@company.com"},
        "assignee": {"id": assignee_id, "token": assignee_token, "email": "test.assignee@company.com"},
        "executive": {"id": executive_id, "token": executive_token, "email": "test.executive@company.com"}
    }


@pytest.fixture()
def auth_headers(seeded_users: dict[str, Any]):
    """Factory for Authorization headers by role."""
    def _factory(role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {seeded_users[role]['token']}"}
    return _factory