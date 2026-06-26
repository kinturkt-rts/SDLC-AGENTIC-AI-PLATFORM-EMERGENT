"""conftest - test fixtures for training-compliance."""
from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from typing import Any

import pytest
from sqlalchemy import String, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

# ── 1. Environment BEFORE any app import
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "training_compliance")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-for-prod")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")

# ── 2. bcrypt compatibility shim
try:
    import bcrypt as _bcrypt_lib
    import app.security as _security_mod

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

# ── 3. UUID TypeDecorator for SQLite
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
    """Replace PG_UUID columns with _UUIDStr so sqlite3 can bind them."""
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID
    for table in metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, PG_UUID):
                col.type = _UUIDStr()

# ── 4. Now import app (AFTER env is set + shims applied)
from fastapi.testclient import TestClient

from app import database as _db_module
from app.database import Base, get_db
from app.main import app
from app.security import create_access_token, hash_password

# ── 5. Engine + session fixtures

def _build_test_engine() -> Engine:
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    schema = os.environ.get("POSTGRES_SCHEMA", "training_compliance")

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


# ── 6. Auth / seed fixtures

@pytest.fixture()
def seed_data(db_session: Session) -> dict:
    """Seed minimal data and return IDs + tokens."""
    from app.models.entities import (
        Course, Department, Employee, JobRole, RoleRequirement, User,
    )

    dept_id = str(uuid.uuid4())
    role_id = str(uuid.uuid4())
    dept = Department(id=dept_id, name="Engineering")
    job_role = JobRole(id=role_id, name="Developer")
    db_session.add_all([dept, job_role])
    db_session.flush()

    # Employees
    mgr_emp_id = str(uuid.uuid4())
    emp1_id = str(uuid.uuid4())
    emp2_id = str(uuid.uuid4())

    mgr_emp = Employee(id=mgr_emp_id, full_name="Manager User", email="manager@example.com",
                       department_id=dept_id, job_role_id=role_id, is_active=True)
    emp1 = Employee(id=emp1_id, full_name="Employee One", email="emp1@example.com",
                    department_id=dept_id, job_role_id=role_id, manager_id=mgr_emp_id, is_active=True)
    emp2 = Employee(id=emp2_id, full_name="Employee Two", email="emp2@example.com",
                    department_id=dept_id, job_role_id=role_id, manager_id=mgr_emp_id, is_active=True)
    db_session.add_all([mgr_emp, emp1, emp2])
    db_session.flush()

    # Users
    hr_user_id = str(uuid.uuid4())
    mgr_user_id = str(uuid.uuid4())
    emp_user_id = str(uuid.uuid4())
    co_user_id = str(uuid.uuid4())

    hr_user = User(id=hr_user_id, employee_id=mgr_emp_id, email="hr@example.com",
                   hashed_password=hash_password("Test123!"), role="hr_admin")
    mgr_user = User(id=mgr_user_id, employee_id=mgr_emp_id, email="mgr@example.com",
                    hashed_password=hash_password("Test123!"), role="manager")
    emp_user = User(id=emp_user_id, employee_id=emp1_id, email="empuser@example.com",
                    hashed_password=hash_password("Test123!"), role="employee")
    co_user = User(id=co_user_id, employee_id=emp2_id, email="co@example.com",
                   hashed_password=hash_password("Test123!"), role="compliance_officer")
    db_session.add_all([hr_user, mgr_user, emp_user, co_user])
    db_session.flush()

    # Course
    course_id = str(uuid.uuid4())
    course = Course(id=course_id, name="Safety 101", category="safety",
                    validity_period_months=12, required_for_all_staff=True, is_active=True)
    db_session.add(course)
    db_session.flush()

    # Role requirement
    req_id = str(uuid.uuid4())
    role_req = RoleRequirement(id=req_id, job_role_id=role_id, course_id=course_id)
    db_session.add(role_req)
    db_session.commit()

    # Create tokens
    hr_token, _ = create_access_token(subject=hr_user_id, role="hr_admin", employee_id=mgr_emp_id)
    mgr_token, _ = create_access_token(subject=mgr_user_id, role="manager", employee_id=mgr_emp_id)
    emp_token, _ = create_access_token(subject=emp_user_id, role="employee", employee_id=emp1_id)
    co_token, _ = create_access_token(subject=co_user_id, role="compliance_officer", employee_id=emp2_id)

    return {
        "dept_id": dept_id,
        "role_id": role_id,
        "mgr_emp_id": mgr_emp_id,
        "emp1_id": emp1_id,
        "emp2_id": emp2_id,
        "course_id": course_id,
        "req_id": req_id,
        "hr_user_id": hr_user_id,
        "hr_token": hr_token,
        "mgr_token": mgr_token,
        "emp_token": emp_token,
        "co_token": co_token,
    }


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
