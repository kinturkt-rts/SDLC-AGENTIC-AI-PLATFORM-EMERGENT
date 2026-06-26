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
  - Add app-specific seed fixtures (users, categories, etc.)
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
from sqlalchemy import String, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator


def _ts(iso: str) -> datetime:
    """ISO string → datetime for ORM TimestampTZ columns in SQLite tests."""
    return datetime.fromisoformat(iso)


# ── 1. Environment BEFORE any app import ─────────────────────────────────────
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "SCHEMA_NAME")  # ADAPT: actual schema
os.environ.setdefault("API_KEY", "test-key")              # ADAPT: if API-key auth
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
    """Stores UUID as 36-char string in SQLite; round-trips to uuid.UUID."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return None
        return uuid.UUID(str(value))


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


# ── 6. Auth fixtures (ADAPT: keep only what the app uses) ───────────────────

# --- API-key variant ---
@pytest.fixture()
def api_headers():
    """Headers for API-key auth apps."""
    return {"X-API-Key": os.environ["API_KEY"]}


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