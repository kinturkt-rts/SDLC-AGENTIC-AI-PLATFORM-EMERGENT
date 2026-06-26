"""Test configuration for support-knowledge-hub."""
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


# -- 1. Environment BEFORE any app import --
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "support_knowledge_hub")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-for-prod")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")
os.environ.setdefault("AWS_REGION", "us-east-2")
os.environ.setdefault("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
os.environ.setdefault("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")

# -- 2. bcrypt compatibility shim --
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


# -- 4. Now import app (AFTER env is set + shims applied) --
from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.security import hash_password, create_access_token  # noqa: E402


# -- 5. Engine + session fixtures --
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


# -- 6. Auth helpers --
def _make_token(user_id: str, role: str) -> str:
    token, _ = create_access_token(subject=user_id, role=role)
    return token


@pytest.fixture()
def seed_users(db_session: Session):
    """Seed users for tests and return tokens."""
    from app.models.user import User

    admin_id = "a1000000-0000-0000-0000-000000000005"
    contributor_id = "a1000000-0000-0000-0000-000000000003"
    contributor2_id = "a1000000-0000-0000-0000-000000000004"
    employee_id = "a1000000-0000-0000-0000-000000000001"
    leadership_id = "a1000000-0000-0000-0000-000000000006"

    users = [
        User(id=admin_id, email="priya@example.com", display_name="Priya", role="knowledge_admin", hashed_password=hash_password("pass123")),
        User(id=contributor_id, email="carol@example.com", display_name="Carol", role="contributor", hashed_password=hash_password("pass123")),
        User(id=contributor2_id, email="dave@example.com", display_name="Dave", role="contributor", hashed_password=hash_password("pass123")),
        User(id=employee_id, email="alice@example.com", display_name="Alice", role="employee", hashed_password=hash_password("pass123")),
        User(id=leadership_id, email="frank@example.com", display_name="Frank", role="leadership", hashed_password=hash_password("pass123")),
    ]
    for u in users:
        db_session.add(u)
    db_session.commit()

    return {
        "admin_id": admin_id,
        "admin_token": _make_token(admin_id, "knowledge_admin"),
        "contributor_id": contributor_id,
        "contributor_token": _make_token(contributor_id, "contributor"),
        "contributor2_id": contributor2_id,
        "contributor2_token": _make_token(contributor2_id, "contributor"),
        "employee_id": employee_id,
        "employee_token": _make_token(employee_id, "employee"),
        "leadership_id": leadership_id,
        "leadership_token": _make_token(leadership_id, "leadership"),
    }


@pytest.fixture()
def seed_category(db_session: Session, seed_users):
    """Seed a category."""
    from app.models.category import Category

    cat_id = "b2000000-0000-0000-0000-000000000001"
    cat = Category(id=cat_id, name="IT", is_active=True, created_by=seed_users["admin_id"])
    db_session.add(cat)
    db_session.commit()
    return cat_id


@pytest.fixture()
def seed_article(db_session: Session, seed_users, seed_category):
    """Seed a published article."""
    from app.models.article import Article

    art_id = "c3000000-0000-0000-0000-000000000001"
    art = Article(
        id=art_id,
        title="How to Reset Your VPN Connection",
        body="If your VPN connection drops or fails to connect, follow these steps.",
        category_id=seed_category,
        tags=["vpn", "network"],
        author_id=seed_users["contributor_id"],
        state="published",
    )
    db_session.add(art)
    db_session.commit()
    return art_id
