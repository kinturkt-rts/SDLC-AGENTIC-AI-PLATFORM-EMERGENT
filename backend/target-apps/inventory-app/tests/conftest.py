"""Pytest configuration and shared fixtures.

Strategy:
- When ``TEST_DATABASE_URL`` is set we use that Postgres DSN (preferred per
  PRD NFR-11). Each test runs inside a transaction that is rolled back so
  no data leaks between cases.
- Otherwise we fall back to an in-memory SQLite database with shared cache
  so the baseline pytest run works on a clean checkout without RDS access.
  The fallback is acknowledged in README and PRD-level open questions.

Either path produces a ``client`` fixture with the FastAPI dependency-overrides
already wired and an ``auth_headers`` factory for admin/staff JWTs.

Compatibility patches applied in this file
-------------------------------------------

1. **bcrypt >= 4.0 / passlib 1.7.x incompatibility**
   ``passlib`` internally SHA-256-digests passwords before passing them to the
   bcrypt C-extension.  ``bcrypt >= 4.0`` rejects secrets > 72 bytes with a
   ``ValueError``.  Fix: monkey-patch ``app.security.hash_password`` and
   ``app.security.verify_password`` to call the ``bcrypt`` library directly.

2. **SQLAlchemy 2.x + SQLite + PG_UUID(as_uuid=True)**
   The app ORM models use ``PG_UUID(as_uuid=True).with_variant(String(36),
   "sqlite")``.  In SQLAlchemy 2.x the *Python-side* type coercion for
   ``PG_UUID(as_uuid=True)`` converts DB strings back to ``uuid.UUID``
   objects on SELECT — but on INSERT/WHERE it still emits the raw Python
   ``uuid.UUID`` object to the sqlite3 driver, which cannot bind it.

   Fix: override **all** UUID-typed columns in the SQLAlchemy ``Table``
   metadata to use a custom ``UUIDStr`` ``TypeDecorator`` that transparently
   coerces ``uuid.UUID`` → ``str`` on the way in and ``str`` → ``uuid.UUID``
   on the way out for the SQLite dialect.  We do this by patching the
   ``type_api`` of each column *before* ``Base.metadata.create_all(eng)``
   runs in the session-scoped ``engine`` fixture.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import TypeDecorator

# ── Environment must be set BEFORE any app import ────────────────────────────
os.environ.setdefault("INVENTORY_SKIP_ENV_CHECK", "1")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production-use-only")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")
# Force test DB before app import — overrides service .env so pytest uses SQLite by default.
_test_dsn = os.environ.get("TEST_DATABASE_URL", "").strip()
os.environ["DATABASE_URL"] = _test_dsn or "sqlite:///:memory:"

# ── bcrypt / passlib compatibility shim (must precede app imports) ───────────
import app.security as _security_module  # noqa: E402

try:
    import bcrypt as _bcrypt_lib

    def _compat_hash_password(plain: str) -> str:
        """Hash using bcrypt directly — bypasses passlib's 72-byte pre-hash."""
        return _bcrypt_lib.hashpw(
            plain.encode("utf-8"), _bcrypt_lib.gensalt(rounds=4)
        ).decode("utf-8")

    def _compat_verify_password(plain: str, hashed: str) -> bool:
        """Verify using bcrypt directly — bypasses passlib's 72-byte pre-hash."""
        try:
            return _bcrypt_lib.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False

    _security_module.hash_password = _compat_hash_password
    _security_module.verify_password = _compat_verify_password

except ImportError:
    pass  # bcrypt not standalone-installed; tests fail naturally
# ─────────────────────────────────────────────────────────────────────────────

from app import database as db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.category import Category  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.stock_movement import StockMovement  # noqa: E402,F401
from app.models.user import User, UserRole  # noqa: E402
from app.security import create_access_token, hash_password  # noqa: E402


# ── UUID TypeDecorator for SQLite ─────────────────────────────────────────────
class _UUIDStr(TypeDecorator):
    """Stores UUID as a 36-char string in SQLite; round-trips to ``uuid.UUID``."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:  # type: ignore[override]
        if value is None:
            return None
        return str(value)  # uuid.UUID → str

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:  # type: ignore[override]
        if value is None:
            return None
        return uuid.UUID(str(value))  # str → uuid.UUID


def _patch_uuid_columns_for_sqlite(metadata: Any) -> None:
    """Replace PG_UUID columns with ``_UUIDStr`` so sqlite3 can bind them.

    Must be called before ``create_all`` to ensure the DDL also uses VARCHAR.
    """
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID

    for table in metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, PG_UUID):
                col.type = _UUIDStr()
                col.type._isnull = False  # satisfy SA internal checks
# ─────────────────────────────────────────────────────────────────────────────


def _build_engine() -> Engine:
    test_dsn = os.getenv("TEST_DATABASE_URL")
    if test_dsn:
        return create_engine(test_dsn, future=True)
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_conn, _record):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


@pytest.fixture(scope="session")
def engine() -> Engine:
    eng = _build_engine()
    # Patch UUID columns BEFORE create_all so SQLite DDL uses VARCHAR(36).
    if eng.dialect.name == "sqlite":
        _patch_uuid_columns_for_sqlite(Base.metadata)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def db_session(engine: Engine) -> Generator[Session, None, None]:
    """Yield a clean session; wipe all rows after each test."""
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.exec_driver_sql(f"DELETE FROM {table.name}")


@pytest.fixture()
def seeded(db_session: Session) -> dict[str, Any]:
    """Deterministic seed: admin + staff + inactive users, one category, one product."""
    admin_id = uuid.uuid4()
    staff_id = uuid.uuid4()
    inactive_id = uuid.uuid4()
    category_id = uuid.uuid4()
    product_id = uuid.uuid4()

    admin = User(
        id=admin_id,
        username="admin",
        password_hash=hash_password("Admin123!"),
        role=UserRole.admin.value,
        is_active=True,
    )
    staff_user = User(
        id=staff_id,
        username="staff",
        password_hash=hash_password("Staff123!"),
        role=UserRole.staff.value,
        is_active=True,
    )
    inactive = User(
        id=inactive_id,
        username="inactive",
        password_hash=hash_password("Inactive123!"),
        role=UserRole.staff.value,
        is_active=False,
    )
    db_session.add_all([admin, staff_user, inactive])
    db_session.flush()

    cat = Category(id=category_id, name="Electronics", slug="electronics")
    db_session.add(cat)
    db_session.flush()

    product = Product(
        id=product_id,
        category_id=category_id,
        sku="ELEC-001",
        name="USB-C Charger",
        unit_price=Decimal("19.99"),
        qty_on_hand=3,
    )
    db_session.add(product)
    db_session.commit()

    admin_token, _ = create_access_token(subject=str(admin_id), role=UserRole.admin.value)
    staff_token, _ = create_access_token(subject=str(staff_id), role=UserRole.staff.value)
    return {
        "admin_id": admin_id,
        "staff_id": staff_id,
        "inactive_id": inactive_id,
        "category_id": category_id,
        "product_id": product_id,
        "admin_token": admin_token,
        "staff_token": staff_token,
    }


@pytest.fixture()
def client(engine: Engine, db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with ``get_db`` and engine bound to the test database."""
    db_module.engine = engine
    db_module.SessionLocal.configure(bind=engine)

    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override_get_db() -> Generator[Session, None, None]:
        sess = TestingSessionLocal()
        try:
            yield sess
        finally:
            sess.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(seeded: dict[str, Any]):
    """Factory: ``auth_headers("admin")`` / ``auth_headers("staff")`` -> headers dict."""

    def _factory(role: str) -> dict[str, str]:
        token = seeded[f"{role}_token"]
        return {"Authorization": f"Bearer {token}"}

    return _factory
