"""Test configuration — SQLite in-memory with schema ATTACH."""
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

# ── 1. Environment BEFORE any app import ─────────────────────────────────────
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "support_knowledge_hub")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-for-prod")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("AWS_REGION", "us-east-2")
os.environ.setdefault("EMBED_MODEL_NAME", "all-MiniLM-L6-v2")
os.environ.setdefault("EMBED_DIM", "384")
os.environ.setdefault("SIMILARITY_THRESHOLD", "0.75")

# ── 2. bcrypt compatibility shim ────────────────────────────────────────
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


# ── 4. Import app (AFTER env is set) ───────────────────────────────────
from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app as application  # noqa: E402
from app.security import hash_password, create_access_token  # noqa: E402

# ── 5. Engine + session fixtures ───────────────────────────────────────

def _build_test_engine() -> Engine:
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    schema = os.environ.get("POSTGRES_SCHEMA", "support_knowledge_hub")

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

    application.dependency_overrides[get_db] = _override
    with TestClient(application) as c:
        yield c
    application.dependency_overrides.clear()


# ── 6. Auth + seed fixtures ───────────────────────────────────────────

SEED_PASSWORD = "KnowledgeHub2024!"


def _ts(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


@pytest.fixture()
def seed_users(db_session: Session):
    """Seed test users for all roles."""
    from app.models.user import User

    hashed = hash_password(SEED_PASSWORD)
    users = {
        "admin": User(
            id="a1000000-0000-0000-0000-000000000001",
            email="priya@example.com",
            display_name="Priya Sharma",
            role="knowledge_admin",
            hashed_password=hashed,
            created_at=_ts("2024-01-05T09:00:00+00:00"),
        ),
        "contributor": User(
            id="a1000000-0000-0000-0000-000000000002",
            email="carlos@example.com",
            display_name="Carlos Rivera",
            role="contributor",
            hashed_password=hashed,
            created_at=_ts("2024-01-06T10:00:00+00:00"),
        ),
        "employee": User(
            id="a1000000-0000-0000-0000-000000000005",
            email="alice@example.com",
            display_name="Alice Johnson",
            role="employee",
            hashed_password=hashed,
            created_at=_ts("2024-01-10T09:30:00+00:00"),
        ),
        "leadership": User(
            id="a1000000-0000-0000-0000-000000000004",
            email="james@example.com",
            display_name="James Wilson",
            role="leadership",
            hashed_password=hashed,
            created_at=_ts("2024-01-08T08:00:00+00:00"),
        ),
    }
    for u in users.values():
        db_session.add(u)
    db_session.commit()
    return users


@pytest.fixture()
def auth_headers(seed_users):
    """Factory: returns auth headers for a given role."""
    def _factory(role: str) -> dict[str, str]:
        user = seed_users[role]
        token, _ = create_access_token(subject=str(user.id), role=user.role)
        return {"Authorization": f"Bearer {token}"}
    return _factory


@pytest.fixture()
def seed_category(db_session: Session, seed_users):
    """Seed a test category."""
    from app.models.category import Category
    cat = Category(
        id="b2000000-0000-0000-0000-000000000001",
        name="IT",
        slug="it",
        created_by="a1000000-0000-0000-0000-000000000001",
        created_at=_ts("2024-01-15T09:00:00+00:00"),
    )
    db_session.add(cat)
    db_session.commit()
    return cat


@pytest.fixture()
def seed_article(db_session: Session, seed_category, seed_users):
    """Seed a published article."""
    from app.models.article import Article
    art = Article(
        id="c3000000-0000-0000-0000-000000000001",
        title="How to Connect to the Corporate VPN",
        body="This guide covers connecting to the corporate VPN from home or public networks.",
        category_id="b2000000-0000-0000-0000-000000000001",
        tags=["vpn", "remote-access"],
        author_id="a1000000-0000-0000-0000-000000000002",
        status="published",
        created_at=_ts("2024-01-20T10:00:00+00:00"),
        updated_at=_ts("2024-01-20T10:00:00+00:00"),
        published_at=_ts("2024-01-20T10:00:00+00:00"),
    )
    db_session.add(art)
    db_session.commit()
    return art
