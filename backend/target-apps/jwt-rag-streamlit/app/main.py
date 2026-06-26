"""Application entry-point.

JWT RAG Streamlit API application.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import health, auth, collections, documents, chat
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
        title="JWT RAG Streamlit API",
        description="Internal Policy RAG Portal with JWT authentication",
        version="1.0.0",
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

    # Include routers
    application.include_router(health.router, prefix="/health", tags=["health"])
    application.include_router(auth.router, prefix="/auth", tags=["authentication"])
    application.include_router(collections.router, prefix="/collections", tags=["collections"])
    application.include_router(documents.router, prefix="/collections", tags=["documents"])
    application.include_router(chat.router, prefix="/collections", tags=["chat"])

    @application.get("/")
    def root() -> dict[str, str]:
        return {"service": settings.service_name, "status": "ok"}

    return application


app = create_app()