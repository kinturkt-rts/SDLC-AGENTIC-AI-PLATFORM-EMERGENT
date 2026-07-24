"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.startup_checks import validate_runtime_config

logger = logging.getLogger(__name__)

# Import models to register them with Base.metadata
import app.models  # noqa: E402, F401

# Auto-create tables on SQLite (dev/test/validator convenience).
# SQLite :memory: requires StaticPool to share one connection across threads.
_settings = get_settings()
_url = (_settings.database_url or "").strip()
if _url.startswith("sqlite"):
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app import database as _db_module
    from app.database import Base

    _sqlite_engine = create_engine(
        _url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(_sqlite_engine, "connect")
    def _sqlite_fk(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(bind=_sqlite_engine)
    _db_module.engine = _sqlite_engine
    _db_module.SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=_sqlite_engine, expire_on_commit=False
    )


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()
    validate_runtime_config(settings)
    yield


app = FastAPI(
    title="Contact Directory API",
    description="Internal REST API for colleague contact cards.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    settings = get_settings()
    if settings.app_env == "development":
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": exc.__class__.__name__},
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── Register routers ──────────────────────────────────────────────────────────
from app.routers import health, departments, contacts  # noqa: E402

app.include_router(health.router)
app.include_router(departments.router, prefix="/api/v1/departments", tags=["departments"])
app.include_router(contacts.router, prefix="/api/v1/contacts", tags=["contacts"])
