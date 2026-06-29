"""Application entry-point — Change Request Hub."""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import health
from app.routers import auth as auth_router
from app.routers import blackout_windows as bw_router
from app.routers import change_requests as cr_router
from app.routers import comments as comments_router
from app.routers import dashboard as dashboard_router
from app.routers import environments as env_router
from app.routers import services as svc_router
from app.routers import users as users_router
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
                content={"detail": str(exc), "type": exc.__class__.__name__},
            )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    # Health (no prefix)
    application.include_router(health.router)

    # All domain routers (no prefix — full paths in decorators)
    application.include_router(auth_router.router, tags=["auth"])
    application.include_router(svc_router.router, tags=["services"])
    application.include_router(env_router.router, tags=["environments"])
    application.include_router(bw_router.router, tags=["blackout-windows"])
    application.include_router(cr_router.router, tags=["change-requests"])
    application.include_router(comments_router.router, tags=["comments"])
    application.include_router(users_router.router, tags=["users"])
    application.include_router(dashboard_router.router, tags=["dashboard"])

    return application


app = create_app()
