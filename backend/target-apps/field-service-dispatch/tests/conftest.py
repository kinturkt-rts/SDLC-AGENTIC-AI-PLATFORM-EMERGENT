"""Test configuration — sets env before app imports, patches UUID for SQLite."""
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
os.environ.setdefault("POSTGRES_SCHEMA", "field_service_dispatch")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-for-prod")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")
os.environ.setdefault("SLA_BREACH_HOUR", "17")

# ── 2. bcrypt compatibility shim ─────────────────────────────────────────────
_SECURITY_MODULE = None
try:
    import app.security as _security_mod
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

# Import all models to ensure they are registered
from app.models.user import User  # noqa: E402, F401
from app.models.technician import Technician  # noqa: E402, F401
from app.models.customer import Customer, ServiceAddress  # noqa: E402, F401
from app.models.work_order import WorkOrder, WorkOrderPart  # noqa: E402, F401
from app.models.status_history import StatusHistory  # noqa: E402, F401

# ── 5. Engine + session fixtures ────────────────────────────────────────────

def _build_test_engine() -> Engine:
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    schema = os.environ.get("POSTGRES_SCHEMA", "field_service_dispatch")

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
                conn.exec_driver_sql(f'DELETE FROM "{table.name}"')


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
def seed_users(db_session: Session) -> dict:
    """Create test users and return auth headers dict by role."""
    tech = Technician(
        id="a1000000-0000-0000-0000-000000000001",
        display_name="Test Tech",
        skills=["residential"],
        is_active=True,
    )
    db_session.add(tech)

    inactive_tech = Technician(
        id="a1000000-0000-0000-0000-000000000099",
        display_name="Inactive Tech",
        skills=["commercial"],
        is_active=False,
    )
    db_session.add(inactive_tech)

    dispatcher_user = User(
        id="b1000000-0000-0000-0000-000000000001",
        username="dispatcher1",
        hashed_password=hash_password("Test123!"),
        role="dispatcher",
        technician_id=None,
    )
    tech_user = User(
        id="b1000000-0000-0000-0000-000000000002",
        username="tech1",
        hashed_password=hash_password("Test123!"),
        role="technician",
        technician_id="a1000000-0000-0000-0000-000000000001",
    )
    owner_user = User(
        id="b1000000-0000-0000-0000-000000000003",
        username="owner1",
        hashed_password=hash_password("Test123!"),
        role="owner",
        technician_id=None,
    )
    db_session.add_all([dispatcher_user, tech_user, owner_user])
    db_session.commit()

    dispatcher_token, _ = create_access_token(
        subject=str(dispatcher_user.id), role="dispatcher"
    )
    tech_token, _ = create_access_token(
        subject=str(tech_user.id), role="technician", technician_id=str(tech.id)
    )
    owner_token, _ = create_access_token(
        subject=str(owner_user.id), role="owner"
    )

    return {
        "dispatcher_headers": {"Authorization": f"Bearer {dispatcher_token}"},
        "technician_headers": {"Authorization": f"Bearer {tech_token}"},
        "owner_headers": {"Authorization": f"Bearer {owner_token}"},
        "technician_id": tech.id,
        "dispatcher_user_id": dispatcher_user.id,
        "tech_user_id": tech_user.id,
    }
