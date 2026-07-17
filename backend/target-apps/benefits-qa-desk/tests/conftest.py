"""Test configuration — SQLite in-memory, JWT auth fixtures."""
from __future__ import annotations

import os
import uuid
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


def _ts(iso: str) -> datetime:
    """ISO string → datetime for ORM TimestampTZ columns in SQLite tests."""
    return datetime.fromisoformat(iso)


# ── 1. Environment BEFORE any app import ──
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "benefits_qa_desk")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-for-prod")
os.environ.setdefault("JWT_TTL_HOURS", "8")
os.environ.setdefault("AWS_REGION", "us-east-2")
os.environ.setdefault("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
os.environ.setdefault("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
os.environ.setdefault("PDF_STORAGE_DIR", "/tmp/test_pdfs")

# ── 2. bcrypt compatibility shim ──
_SECURITY_MODULE = None
try:
    import app.security as _security_mod  # noqa: E402
    _SECURITY_MODULE = _security_mod
except ImportError:
    pass

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


# ── 4. Now import app (AFTER env is set + shims applied) ──
from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
import app.models  # noqa: E402, F401

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


# ── 6. Auth fixtures (JWT) ──
from app.security import create_access_token, hash_password  # noqa: E402
from app.models.user import User  # noqa: E402


@pytest.fixture()
def seed_users(db_session: Session) -> dict:
    """Create admin, contributor, employee users and return tokens + IDs."""
    admin_id = str(uuid.uuid4())
    contributor_id = str(uuid.uuid4())
    employee_id = str(uuid.uuid4())

    pw_hash = hash_password("TestPass1!")

    admin = User(id=admin_id, username="admin_test", hashed_password=pw_hash, role="admin", is_active=True)
    contributor = User(id=contributor_id, username="contributor_test", hashed_password=pw_hash, role="contributor", is_active=True)
    employee = User(id=employee_id, username="employee_test", hashed_password=pw_hash, role="employee", is_active=True)

    db_session.add_all([admin, contributor, employee])
    db_session.commit()

    admin_token = create_access_token(subject=admin_id, role="admin", username="admin_test")
    contributor_token = create_access_token(subject=contributor_id, role="contributor", username="contributor_test")
    employee_token = create_access_token(subject=employee_id, role="employee", username="employee_test")

    return {
        "admin_id": admin_id,
        "contributor_id": contributor_id,
        "employee_id": employee_id,
        "admin_token": admin_token,
        "contributor_token": contributor_token,
        "employee_token": employee_token,
    }


@pytest.fixture()
def admin_headers(seed_users: dict) -> dict:
    return {"Authorization": f"Bearer {seed_users['admin_token']}"}


@pytest.fixture()
def contributor_headers(seed_users: dict) -> dict:
    return {"Authorization": f"Bearer {seed_users['contributor_token']}"}


@pytest.fixture()
def employee_headers(seed_users: dict) -> dict:
    return {"Authorization": f"Bearer {seed_users['employee_token']}"}
