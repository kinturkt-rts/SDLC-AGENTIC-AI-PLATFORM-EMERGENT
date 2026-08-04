"""REFERENCE conftest.py for developer-agent generated Postgres apps.

Copy and adapt for each target-app. This handles:
  1. Env-before-import pattern (DATABASE_URL, POSTGRES_SCHEMA, auth secrets)
  2. bcrypt >= 4.0 / passlib 1.7.x compatibility shim
  3. PG_UUID(as_uuid=True) → SQLite TypeDecorator patching
  4. Schema-qualified table attachment for SQLite
  5. Session-scoped engine + function-scoped rollback sessions
  6. TestClient with dependency override
  7. Auth fixture factories (JWT + API-key variants)

Adapt checklist:
  - Replace SCHEMA_NAME with actual POSTGRES_SCHEMA value
  - Replace JWT/API-key env vars to match the app's config.py
  - Add app-specific seed fixtures (import models from app.models.* inside fixtures)
  - For TimestampTZ columns: use `_ts("2024-01-01T00:00:00+00:00")` in fixtures — not bare ISO strings
  - Remove auth sections not needed (JWT or API-key, not both)
"""
from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import String
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import TypeDecorator


def _ts(iso: str) -> datetime:
    """ISO string → datetime for ORM TimestampTZ columns in SQLite tests."""
    return datetime.fromisoformat(iso)


# ── 1. Environment BEFORE any app import ─────────────────────────────────────
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
# Tests run against a REAL Postgres schema built from db/sql/*.sql (see
# developer-agent's _setup_temp_pg_test_schema), never SQLite. SQLite silently
# accepts any Python value in a "enum" column, which made ORM-vs-DDL drift (a
# column the SQL declares as a native Postgres ENUM but the ORM types as a plain
# String) invisible to pytest — the DB was always built FROM the same ORM model
# under test, so it could never disagree with it. There is no SQLite fallback:
# if DATABASE_URL isn't set, fail loud here rather than silently passing on a
# database that structurally cannot catch this class of bug.
if not os.environ.get("DATABASE_URL"):
    raise RuntimeError(
        "DATABASE_URL is not set. Tests require a real Postgres connection string "
        "pointing at a schema built from this app's db/sql/*.sql (normally supplied "
        "by the developer-agent validation gate's _setup_temp_pg_test_schema). "
        "There is no SQLite fallback — set DATABASE_URL and POSTGRES_SCHEMA "
        "yourself for a manual run."
    )
os.environ.setdefault("POSTGRES_SCHEMA", "SCHEMA_NAME")  # ADAPT: actual schema
# api-key mode has no shared-secret env var — auth is per-user tokens seeded
# into the users table; see the "API-key variant" fixtures below.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-for-prod")  # ADAPT: if JWT auth
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")

# ── 2. bcrypt / passlib compatibility shim ───────────────────────────────────
# passlib 1.7.x pre-hashes passwords with SHA-256 (producing >72 bytes),
# which bcrypt >= 4.0 rejects. This shim calls bcrypt directly.
# Safe to remove when passlib releases a compatible version.
_SECURITY_MODULE = None
try:
    import app.security as _security_mod  # noqa: E402
    _SECURITY_MODULE = _security_mod
except ImportError:
    pass  # no security module = no JWT app; skip shim

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
        pass  # bcrypt not standalone-installed

# ── 3. UUID TypeDecorator for SQLite ─────────────────────────────────────────
class _UUIDStr(TypeDecorator):
    """Stores UUID as 36-char string in SQLite; round-trips to str."""
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

# ── 4. Now import app (AFTER env is set + shims applied) ────────────────────
from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
# Register ORM models with Base.metadata. `import app.models` binds local name `app`
# to the package — always use `fastapi_app` (never bare `app`) for TestClient/overrides.
import app.models  # noqa: E402, F401

# ── 5. Engine + session fixtures ────────────────────────────────────────────

def _build_test_engine() -> Engine:
    """Reuse the app's own production engine (app/database.py's _make_engine) —
    it already handles Postgres schema binding and search_path correctly via
    POSTGRES_SCHEMA, which was set above BEFORE app.database was imported.
    Building a second, separate engine here would just duplicate that logic and
    risk it silently drifting from what the real app actually does."""
    return _db_module.engine


@pytest.fixture(scope="session")
def engine() -> Engine:
    eng = _build_test_engine()
    if eng.dialect.name == "sqlite":
        # Defensive only — DATABASE_URL is required to be a real Postgres URL
        # above, so this branch never runs in the developer-agent gate; kept in
        # case someone points a manual run at SQLite anyway.
        _patch_uuid_columns_for_sqlite(Base.metadata)
    # Deliberately NOT Base.metadata.create_all(eng): the schema (including
    # native Postgres enums) is already built from db/sql/*.sql before pytest
    # runs. Creating tables from the ORM here would make ORM-vs-DDL drift (e.g.
    # a SQL enum typed as plain String in the ORM) structurally undetectable —
    # the DB would always match whatever the ORM under test says.
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


# ── 6. Auth fixtures (ADAPT: keep only what the app uses) ───────────────────

# --- API-key variant (per-user token + role, looked up via app/dependencies.py) ---
# Uncomment + adapt: seed one user per role your app's RBAC needs, each with its
# own distinct token, then build headers from the seeded token — never a shared
# secret, never a second header.
#
# @pytest.fixture()
# def seeded_users(db_session):
#     """Seed users across roles with distinct tokens; return their tokens."""
#     from app.models.user import User
#     users = {
#         "employee": User(token="tok_employee_test", role="employee"),
#         "manager": User(token="tok_manager_test", role="manager"),
#         "admin": User(token="tok_admin_test", role="admin"),
#     }
#     db_session.add_all(users.values())
#     db_session.commit()
#     return {role: user.token for role, user in users.items()}
#
# @pytest.fixture()
# def api_headers(seeded_users):
#     def _factory(role: str = "employee"):
#         return {"X-API-Key": seeded_users[role]}
#     return _factory


# --- JWT variant (uncomment + adapt when app uses JWT) ---
# from app.security import create_access_token, hash_password
#
# @pytest.fixture()
# def seeded(db_session):
#     """Seed admin + staff users; return tokens and IDs."""
#     admin_id = uuid.uuid4()
#     staff_id = uuid.uuid4()
#     # ... add User rows with hash_password("Admin123!") etc.
#     db_session.commit()
#     admin_token, _ = create_access_token(subject=str(admin_id), role="admin")
#     staff_token, _ = create_access_token(subject=str(staff_id), role="staff")
#     return {"admin_token": admin_token, "staff_token": staff_token, ...}
#
# @pytest.fixture()
# def auth_headers(seeded):
#     def _factory(role: str):
#         return {"Authorization": f"Bearer {seeded[f'{role}_token']}"}
#     return _factory