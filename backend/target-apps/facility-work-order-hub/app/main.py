"""Application entry-point."""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import health
from app.routers import auth
from app.routers import sites
from app.routers import locations
from app.routers import work_orders
from app.routers import comments
from app.routers import dashboard
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

    application.include_router(health.router)
    application.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    application.include_router(sites.router, prefix="/api/v1/sites", tags=["sites"])
    application.include_router(locations.router, prefix="/api/v1/sites/{site_id}/locations", tags=["locations"])
    application.include_router(work_orders.router, prefix="/api/v1/work-orders", tags=["work-orders"])
    application.include_router(comments.router, prefix="/api/v1/work-orders/{work_order_id}/comments", tags=["comments"])
    application.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])

    @application.get("/")
    def root() -> dict[str, str]:
        return {"service": settings.service_name, "status": "ok"}

    return application


app = create_app()
