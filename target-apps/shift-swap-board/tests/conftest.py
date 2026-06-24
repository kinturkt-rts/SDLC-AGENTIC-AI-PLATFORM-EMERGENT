"""Test configuration for shift-swap-board."""
from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import date, datetime, timedelta, timezone
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


# ── 1. Environment BEFORE any app import ───────────────────────────────────
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "shift_swap_board")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-for-prod")
os.environ.setdefault("JWT_EXPIRY_HOURS", "8")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

# ── 2. bcrypt shim ─────────────────────────────────────────────────────────
try:
    import app.security as _security_mod  # noqa: E402
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

# ── 3. UUID TypeDecorator for SQLite ─────────────────────────────────────
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


# ── 4. Import app (AFTER env is set) ────────────────────────────────────
from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

# ── 5. Engine + session fixtures ────────────────────────────────────────

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

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── 6. Auth + seed fixtures ────────────────────────────────────────────
from app.security import create_access_token, hash_password  # noqa: E402
from app.models import User, StaffProfile, ShiftRoster, FloorLeadWeek, SwapRequest, SwapAuditLog  # noqa: E402


@pytest.fixture()
def seeded(db_session: Session):
    """Seed users, profiles, roster, floor-lead weeks for tests."""
    admin_id = str(uuid.uuid4())
    lead_id = str(uuid.uuid4())
    staff1_id = str(uuid.uuid4())
    staff2_id = str(uuid.uuid4())

    now = datetime.now(timezone.utc)

    admin = User(id=admin_id, username="admin", password_hash=hash_password("Password1!"),
                 role="admin", display_name="Admin User", is_active=True, created_at=now)
    lead = User(id=lead_id, username="lead_a", password_hash=hash_password("Password1!"),
                role="floor_lead", display_name="Lead A", is_active=True, created_at=now)
    staff1 = User(id=staff1_id, username="staff_01", password_hash=hash_password("Password1!"),
                  role="staff", display_name="Staff One", is_active=True, created_at=now)
    staff2 = User(id=staff2_id, username="staff_02", password_hash=hash_password("Password1!"),
                  role="staff", display_name="Staff Two", is_active=True, created_at=now)

    db_session.add_all([admin, lead, staff1, staff2])
    db_session.flush()

    # Staff profiles
    sp1_id = str(uuid.uuid4())
    sp2_id = str(uuid.uuid4())
    lead_sp_id = str(uuid.uuid4())
    sp1 = StaffProfile(id=sp1_id, user_id=staff1_id)
    sp2 = StaffProfile(id=sp2_id, user_id=staff2_id)
    lead_sp = StaffProfile(id=lead_sp_id, user_id=lead_id)
    db_session.add_all([sp1, sp2, lead_sp])
    db_session.flush()

    # Roster rows (future dates)
    today = date.today()
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)

    shift1_id = str(uuid.uuid4())
    shift2_id = str(uuid.uuid4())
    shift3_id = str(uuid.uuid4())

    shift1 = ShiftRoster(id=shift1_id, staff_id=sp1_id, shift_date=tomorrow, shift_window="morning", created_at=now)
    shift2 = ShiftRoster(id=shift2_id, staff_id=sp1_id, shift_date=day_after, shift_window="afternoon", created_at=now)
    shift3 = ShiftRoster(id=shift3_id, staff_id=sp2_id, shift_date=tomorrow, shift_window="afternoon", created_at=now)
    db_session.add_all([shift1, shift2, shift3])
    db_session.flush()

    # Floor lead week for this week
    monday = today - timedelta(days=today.weekday())
    flw = FloorLeadWeek(id=str(uuid.uuid4()), week_start=monday, floor_lead_user_id=lead_id)
    db_session.add(flw)
    db_session.commit()

    # Tokens
    admin_token = create_access_token(subject=admin_id, role="admin")
    lead_token = create_access_token(subject=lead_id, role="floor_lead")
    staff1_token = create_access_token(subject=staff1_id, role="staff")
    staff2_token = create_access_token(subject=staff2_id, role="staff")

    return {
        "admin_id": admin_id,
        "lead_id": lead_id,
        "staff1_id": staff1_id,
        "staff2_id": staff2_id,
        "sp1_id": sp1_id,
        "sp2_id": sp2_id,
        "lead_sp_id": lead_sp_id,
        "shift1_id": shift1_id,
        "shift2_id": shift2_id,
        "shift3_id": shift3_id,
        "admin_token": admin_token,
        "lead_token": lead_token,
        "staff1_token": staff1_token,
        "staff2_token": staff2_token,
        "monday": monday,
        "tomorrow": tomorrow,
        "day_after": day_after,
    }


@pytest.fixture()
def auth_headers(seeded):
    """Factory for auth headers by role name."""
    def _factory(role: str):
        token_key = f"{role}_token"
        if token_key not in seeded:
            # Try staff1, lead, admin
            mapping = {"staff": "staff1_token", "floor_lead": "lead_token", "admin": "admin_token"}
            token_key = mapping.get(role, token_key)
        return {"Authorization": f"Bearer {seeded[token_key]}"}
    return _factory
