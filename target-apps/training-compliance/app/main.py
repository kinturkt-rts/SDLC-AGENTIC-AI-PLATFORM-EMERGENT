"""Application entry-point."""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import health, auth, courses, employees, requirements, completions, compliance, reports, alerts
from app.startup_checks import validate_runtime_config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    validate_runtime_config(settings)
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

    # Health (no prefix — route is /health)
    application.include_router(health.router)

    # Domain routers
    application.include_router(auth.router, prefix="/auth", tags=["auth"])
    application.include_router(courses.router, prefix="/courses", tags=["courses"])
    application.include_router(employees.router, prefix="/employees", tags=["employees"])
    application.include_router(requirements.router, prefix="/requirements", tags=["requirements"])
    application.include_router(completions.router, prefix="/completions", tags=["completions"])
    application.include_router(compliance.router, prefix="/compliance", tags=["compliance"])
    application.include_router(reports.router, prefix="/reports", tags=["reports"])
    application.include_router(alerts.router, prefix="/alerts", tags=["alerts"])

    @application.get("/")
    def root() -> dict[str, str]:
        return {"service": settings.service_name, "status": "ok"}

    return application


app = create_app()
