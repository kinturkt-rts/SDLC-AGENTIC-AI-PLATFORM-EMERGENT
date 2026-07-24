"""Application entry-point (api-key mode — no login flow, no auth router).

Replace 'service-template' with the real service name. Add domain routers
below the health router in the order they appear in design §4.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import health
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

    # No auth router in api-key mode — there is no login flow. Routes that need
    # auth use require_api_key (app/dependencies.py) directly on the route.
    application.include_router(health.router)
    # TODO: add domain routers — e.g. application.include_router(items.router, prefix="/items")

    @application.get("/")
    def root() -> dict[str, str]:
        return {"service": settings.service_name, "status": "ok"}

    return application


app = create_app()
