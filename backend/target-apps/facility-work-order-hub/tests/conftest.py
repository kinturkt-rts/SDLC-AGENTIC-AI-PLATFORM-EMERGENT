"""Test conftest for facility-work-order-hub.

Handles:
  1. Env-before-import pattern
  2. bcrypt shim
  3. PG_UUID SQLite patching
  4. Schema-qualified attach
  5. Session fixtures
  6. TestClient with dependency override
  7. JWT auth fixtures
"""
from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
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


# ── 1. Environment BEFORE any app import ─────────────────────────────────────
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "facility_work_order_hub")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-for-prod")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")

# ── 2. bcrypt / passlib compatibility shim ───────────────────────────────────
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


# ── 6. Auth + seed fixtures ──────────────────────────────────────────────────

@pytest.fixture()
def seed_users(db_session: Session) -> dict:
    """Seed users for all four roles. Returns dict with IDs and tokens."""
    from app.models.user import User

    users_data = [
        {"id": str(uuid.uuid4()), "email": "admin@test.com", "display_name": "Admin User", "role": "facilities_admin"},
        {"id": str(uuid.uuid4()), "email": "tech@test.com", "display_name": "Tech User", "role": "technician"},
        {"id": str(uuid.uuid4()), "email": "requester@test.com", "display_name": "Requester User", "role": "requester"},
        {"id": str(uuid.uuid4()), "email": "leader@test.com", "display_name": "Leader User", "role": "leadership"},
        {"id": str(uuid.uuid4()), "email": "tech2@test.com", "display_name": "Tech2 User", "role": "technician"},
    ]

    result = {}
    for u in users_data:
        user = User(
            id=u["id"],
            email=u["email"],
            hashed_password=hash_password("TestPass123!"),
            display_name=u["display_name"],
            role=u["role"],
        )
        db_session.add(user)
        result[u["role"]] = {
            "id": u["id"],
            "email": u["email"],
            "display_name": u["display_name"],
            "token": create_access_token(subject=u["id"], role=u["role"], email=u["email"]),
        }
        if u["role"] == "technician" and "technician2" not in result:
            if "technician" in result:
                result["technician2"] = {
                    "id": u["id"],
                    "email": u["email"],
                    "display_name": u["display_name"],
                    "token": create_access_token(subject=u["id"], role=u["role"], email=u["email"]),
                }

    db_session.commit()
    return result


@pytest.fixture()
def seed_site(db_session: Session) -> dict:
    """Seed an active site."""
    from app.models.site import Site

    site_id = str(uuid.uuid4())
    site = Site(
        id=site_id,
        site_code="TEST-01",
        name="Test Site",
        address_line="123 Test Street",
        active=True,
    )
    db_session.add(site)
    db_session.commit()
    return {"id": site_id, "site_code": "TEST-01"}


@pytest.fixture()
def auth_headers(seed_users: dict):
    """Factory for auth headers by role."""
    def _factory(role: str) -> dict:
        return {"Authorization": f"Bearer {seed_users[role]['token']}"}
    return _factory
