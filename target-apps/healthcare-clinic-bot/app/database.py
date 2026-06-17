"""SQLAlchemy engine, session, and Base setup."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

_connect_args: dict = {}
_engine_kwargs: dict = {"future": True}

if settings.database_url.startswith("sqlite"):
    _connect_args["check_same_thread"] = False
else:
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    **_engine_kwargs,
)

# Set search_path for Postgres
if not settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute(f"SET search_path TO {settings.postgres_schema}, public")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a session, closes on completion."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
