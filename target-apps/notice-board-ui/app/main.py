"""Application entry-point for Team Notice Board."""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import health, notices, categories
from app.startup_checks import validate_runtime_config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    validate_runtime_config(settings)

    # Auto-create tables for SQLite (test/smoke/import-probe environments).
    # In production Postgres, migrations handle schema creation.
    from app.database import create_tables_if_sqlite  # noqa: PLC0415
    create_tables_if_sqlite()

    logger.info("startup_checks_passed service=%s", settings.service_name)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Team Notice Board",
        description="Company announcements with scheduling and archival support.",
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
                content={"detail": str(exc), "type": exc.__class__.__name__},
            )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    application.include_router(health.router)
    application.include_router(notices.router, prefix="/api/v1/notices", tags=["notices"])
    application.include_router(categories.router, prefix="/api/v1/categories", tags=["categories"])

    @application.get("/")
    def root() -> dict[str, str]:
        return {"service": settings.service_name, "status": "ok"}

    return application


app = create_app()
