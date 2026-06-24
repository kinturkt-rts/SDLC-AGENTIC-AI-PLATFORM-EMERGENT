"""Application entry-point for Platform Desk."""
from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import health
from app.routers import services as services_router
from app.routers import runbooks as runbooks_router
from app.routers import search as search_router
from app.routers import incident_touches as touches_router
from app.routers import admin as admin_router
from app.startup_checks import validate_runtime_config

logger = logging.getLogger(__name__)


def _ensure_tables():
    """Create tables for SQLite (dev/validation mode)."""
    from app.database import Base, engine
    url = str(engine.url)
    if url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    validate_runtime_config(settings)
    _ensure_tables()
    logger.info("startup_checks_passed service=%s", settings.service_name)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.service_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error path=%s", request.url.path)
        if (settings.app_env or "").strip().lower() == "development":
            return JSONResponse(
                status_code=500,
                content={
                    "detail": str(exc),
                    "type": exc.__class__.__name__,
                },
            )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    application.include_router(health.router)
    application.include_router(services_router.router)
    application.include_router(runbooks_router.router)
    application.include_router(search_router.router)
    application.include_router(touches_router.router)
    application.include_router(admin_router.router)

    @application.get("/")
    def root() -> dict[str, str]:
        return {"service": settings.service_name, "status": "ok"}

    return application


app = create_app()

# Ensure tables exist for SQLite when lifespan may not be triggered (e.g. testing tools)
if os.environ.get("SKIP_STARTUP_CHECKS", "").strip().lower() in ("1", "true", "yes"):
    _ensure_tables()
