"""Test conftest for field-service-dispatch."""
from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import datetime, date, timezone
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


# -- 1. Environment BEFORE any app import --
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "field_service_dispatch")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("SLA_CUTOFF_HOUR", "17")

# -- 2. bcrypt compatibility shim --
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

# -- 3. UUID TypeDecorator for SQLite --
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


# -- 4. Import app AFTER env --
from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
import app.models  # noqa: E402, F401


# -- 5. Engine + session fixtures --
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


# -- 6. Auth fixtures (API-key variant) --
@pytest.fixture()
def api_headers():
    return {"X-API-Key": "test-key"}


# -- 7. Seed fixtures --
@pytest.fixture()
def seed_data(db_session: Session) -> dict:
    """Seed users, technicians, customers, and work orders for tests."""
    from app.models.technician import Technician
    from app.models.customer import Customer
    from app.models.user import User
    from app.models.work_order import WorkOrder
    from app.models.assignment import Assignment
    from app.models.audit_log import AuditLog
    from app.security import hash_password

    # Technicians
    tech1_id = str(uuid.uuid4())
    tech2_id = str(uuid.uuid4())
    tech_inactive_id = str(uuid.uuid4())

    tech1 = Technician(id=tech1_id, name="Carlos Mendez", skills=["residential", "commercial"], active=True, created_at=_ts("2024-01-15T08:00:00+00:00"))
    tech2 = Technician(id=tech2_id, name="Janice Park", skills=["residential", "install"], active=True, created_at=_ts("2024-01-15T08:00:00+00:00"))
    tech_inactive = Technician(id=tech_inactive_id, name="Derek Johnson", skills=["commercial"], active=False, created_at=_ts("2024-02-01T08:00:00+00:00"))
    db_session.add_all([tech1, tech2, tech_inactive])
    db_session.flush()

    # Users
    dispatcher_id = str(uuid.uuid4())
    tech_user_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())

    dispatcher = User(
        id=dispatcher_id, username="dana_dispatch",
        hashed_password=hash_password("FieldService2024!"),
        role="dispatcher", technician_id=None, api_key="test-key"
    )
    tech_user = User(
        id=tech_user_id, username="carlos_tech",
        hashed_password=hash_password("FieldService2024!"),
        role="technician", technician_id=tech1_id, api_key="tech-key"
    )
    owner_user = User(
        id=owner_id, username="frank_owner",
        hashed_password=hash_password("FieldService2024!"),
        role="owner", technician_id=None, api_key="owner-key"
    )
    db_session.add_all([dispatcher, tech_user, owner_user])
    db_session.flush()

    # Customer
    cust_id = str(uuid.uuid4())
    cust = Customer(
        id=cust_id, full_name="Lakewood Medical Center",
        phone="614-555-0101", email="facilities@lakewoodmed.com",
        street="2200 Olentangy River Rd", city="Columbus", state="OH", zip="43210",
        created_at=_ts("2024-01-20T09:00:00+00:00")
    )
    db_session.add(cust)
    db_session.flush()

    # Work orders
    wo_new_id = str(uuid.uuid4())
    wo_assigned_id = str(uuid.uuid4())
    wo_in_progress_id = str(uuid.uuid4())
    wo_completed_id = str(uuid.uuid4())

    today = date.today()
    wo_new = WorkOrder(
        id=wo_new_id, customer_id=cust_id, description="AC maintenance",
        priority="routine", scheduled_date=today, time_window="morning",
        status="new", created_at=_ts("2024-06-01T08:00:00+00:00"),
        updated_at=_ts("2024-06-01T08:00:00+00:00")
    )
    wo_assigned = WorkOrder(
        id=wo_assigned_id, customer_id=cust_id, description="Furnace repair",
        priority="urgent", scheduled_date=today, time_window="afternoon",
        status="assigned", created_at=_ts("2024-06-01T08:00:00+00:00"),
        updated_at=_ts("2024-06-01T08:00:00+00:00")
    )
    wo_in_progress = WorkOrder(
        id=wo_in_progress_id, customer_id=cust_id, description="Heat pump check",
        priority="routine", scheduled_date=today, time_window="all_day",
        status="in_progress", created_at=_ts("2024-06-01T08:00:00+00:00"),
        updated_at=_ts("2024-06-01T08:00:00+00:00")
    )
    wo_completed = WorkOrder(
        id=wo_completed_id, customer_id=cust_id, description="Thermostat install",
        priority="routine", scheduled_date=today, time_window="morning",
        status="completed", completion_notes="Installed and tested.",
        created_at=_ts("2024-06-01T08:00:00+00:00"),
        updated_at=_ts("2024-06-01T08:00:00+00:00")
    )
    db_session.add_all([wo_new, wo_assigned, wo_in_progress, wo_completed])
    db_session.flush()

    # Assignments for assigned and in_progress orders
    assgn1 = Assignment(
        id=str(uuid.uuid4()), work_order_id=wo_assigned_id,
        technician_id=tech1_id, assigned_by=dispatcher_id, is_active=True,
        assigned_at=_ts("2024-06-01T09:00:00+00:00")
    )
    assgn2 = Assignment(
        id=str(uuid.uuid4()), work_order_id=wo_in_progress_id,
        technician_id=tech1_id, assigned_by=dispatcher_id, is_active=True,
        assigned_at=_ts("2024-06-01T09:00:00+00:00")
    )
    db_session.add_all([assgn1, assgn2])
    db_session.flush()

    # Audit log entries for assigned and in_progress orders
    audit1 = AuditLog(
        id=str(uuid.uuid4()), work_order_id=wo_assigned_id,
        from_status="new", to_status="assigned",
        actor_id=dispatcher_id, actor_role="dispatcher",
        changed_at=_ts("2024-06-01T09:00:00+00:00")
    )
    audit2 = AuditLog(
        id=str(uuid.uuid4()), work_order_id=wo_in_progress_id,
        from_status="new", to_status="assigned",
        actor_id=dispatcher_id, actor_role="dispatcher",
        changed_at=_ts("2024-06-01T09:00:00+00:00")
    )
    audit3 = AuditLog(
        id=str(uuid.uuid4()), work_order_id=wo_in_progress_id,
        from_status="assigned", to_status="in_progress",
        actor_id=tech_user_id, actor_role="technician",
        changed_at=_ts("2024-06-01T10:00:00+00:00")
    )
    db_session.add_all([audit1, audit2, audit3])
    db_session.commit()

    return {
        "dispatcher_id": dispatcher_id,
        "tech_user_id": tech_user_id,
        "owner_id": owner_id,
        "tech1_id": tech1_id,
        "tech2_id": tech2_id,
        "tech_inactive_id": tech_inactive_id,
        "customer_id": cust_id,
        "wo_new_id": wo_new_id,
        "wo_assigned_id": wo_assigned_id,
        "wo_in_progress_id": wo_in_progress_id,
        "wo_completed_id": wo_completed_id,
        "dispatcher_key": "test-key",
        "tech_key": "tech-key",
        "owner_key": "owner-key",
    }


@pytest.fixture()
def dispatcher_headers(seed_data):
    return {"X-API-Key": seed_data["dispatcher_key"]}


@pytest.fixture()
def tech_headers(seed_data):
    return {"X-API-Key": seed_data["tech_key"]}


@pytest.fixture()
def owner_headers(seed_data):
    return {"X-API-Key": seed_data["owner_key"]}
