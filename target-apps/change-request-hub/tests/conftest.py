"""Test configuration — SQLite in-memory with schema ATTACH."""
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
    return datetime.fromisoformat(iso)


# 1. Env BEFORE any app import
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "change_request_hub")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-for-prod")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")

# 2. bcrypt compatibility shim
try:
    import app.security as _security_mod
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


# 3. UUID TypeDecorator for SQLite
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


# 4. Import app AFTER env set
from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.security import create_access_token, hash_password  # noqa: E402


# 5. Engine + session fixtures
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


# 6. Auth helpers
@pytest.fixture()
def seed_users(db_session: Session) -> dict:
    """Seed users for testing. Returns dict with user IDs and tokens."""
    from app.models.user import User

    manager_id = str(uuid.uuid4())
    requester_id = str(uuid.uuid4())
    implementer_id = str(uuid.uuid4())
    leadership_id = str(uuid.uuid4())

    hashed = hash_password("TestPass123!")

    users = [
        User(id=manager_id, email="manager@test.com", password_hash=hashed, display_name="Manager", role="manager"),
        User(id=requester_id, email="requester@test.com", password_hash=hashed, display_name="Requester", role="requester"),
        User(id=implementer_id, email="implementer@test.com", password_hash=hashed, display_name="Implementer", role="implementer"),
        User(id=leadership_id, email="leadership@test.com", password_hash=hashed, display_name="Leadership", role="leadership"),
    ]
    for u in users:
        db_session.add(u)
    db_session.commit()

    mgr_token, _ = create_access_token(subject=manager_id, role="manager")
    req_token, _ = create_access_token(subject=requester_id, role="requester")
    impl_token, _ = create_access_token(subject=implementer_id, role="implementer")
    lead_token, _ = create_access_token(subject=leadership_id, role="leadership")

    return {
        "manager_id": manager_id,
        "requester_id": requester_id,
        "implementer_id": implementer_id,
        "leadership_id": leadership_id,
        "manager_token": mgr_token,
        "requester_token": req_token,
        "implementer_token": impl_token,
        "leadership_token": lead_token,
    }


@pytest.fixture()
def manager_headers(seed_users) -> dict:
    return {"Authorization": f"Bearer {seed_users['manager_token']}"}


@pytest.fixture()
def requester_headers(seed_users) -> dict:
    return {"Authorization": f"Bearer {seed_users['requester_token']}"}


@pytest.fixture()
def implementer_headers(seed_users) -> dict:
    return {"Authorization": f"Bearer {seed_users['implementer_token']}"}


@pytest.fixture()
def leadership_headers(seed_users) -> dict:
    return {"Authorization": f"Bearer {seed_users['leadership_token']}"}


@pytest.fixture()
def sample_service(db_session: Session) -> str:
    from app.models.service import Service
    svc_id = str(uuid.uuid4())
    svc = Service(id=svc_id, name="Test Service", owner_team="TestTeam", tier="tier1", active=True)
    db_session.add(svc)
    db_session.commit()
    return svc_id


@pytest.fixture()
def sample_environment(db_session: Session) -> str:
    from app.models.environment import Environment
    env_id = str(uuid.uuid4())
    env = Environment(id=env_id, name="test-env", sort_order=1, active=True)
    db_session.add(env)
    db_session.commit()
    return env_id
