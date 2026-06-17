"""SQLAlchemy engine, session, and Base — dialect-guarded for SQLite/Postgres."""
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import get_settings

_settings = get_settings()

_is_sqlite = _settings.database_url.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        _settings.database_url,
        connect_args={"check_same_thread": False},
        future=True,
    )
else:
    engine = create_engine(
        _settings.database_url,
        pool_size=5,
        max_overflow=10,
        future=True,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


@event.listens_for(engine, "connect")
def _set_search_path(dbapi_conn, _connection_record):
    """Set schema search_path for Postgres; enable FKs + attach schema for SQLite."""
    if _is_sqlite:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        schema = _settings.postgres_schema
        if schema and schema != "public":
            try:
                cur.execute(f"ATTACH DATABASE ':memory:' AS \"{schema}\"")
            except Exception:
                pass
        cur.close()
    else:
        cur = dbapi_conn.cursor()
        cur.execute(f"SET search_path TO {_settings.postgres_schema}, public")
        cur.close()


def get_db() -> Generator[Session, None, None]:
    """Yield a database session; ensure it is always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
