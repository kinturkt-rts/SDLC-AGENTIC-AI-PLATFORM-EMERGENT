"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.startup_checks import validate_runtime_config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()
    validate_runtime_config(settings)
    yield


app = FastAPI(
    title="Team FAQ Bot",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
settings = get_settings()
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dev exception handler
@app.exception_handler(Exception)
async def _global_exc_handler(request: Request, exc: Exception):
    if get_settings().app_env == "development":
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": exc.__class__.__name__},
        )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── Routers ───────────────────────────────────────────────────────────────────
from app.routers import health, ask, upload, gaps  # noqa: E402

app.include_router(health.router)
app.include_router(ask.router, prefix="/api/v1", tags=["ask"])
app.include_router(upload.router, prefix="/api/v1", tags=["upload"])
app.include_router(gaps.router, prefix="/api/v1", tags=["gaps"])
