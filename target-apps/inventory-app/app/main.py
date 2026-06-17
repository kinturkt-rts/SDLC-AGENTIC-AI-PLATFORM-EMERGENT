"""FastAPI application entrypoint for Inventory Desk."""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, categories, products

logger = logging.getLogger("inventory_desk")
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
    """Validate required env vars at startup (FR-12).

    Tests set `INVENTORY_SKIP_ENV_CHECK=1` to bypass — they inject their own
    Postgres or SQLite engine via the `tests/conftest.py` fixture.
    """
    if not os.getenv("INVENTORY_SKIP_ENV_CHECK"):
        settings.validate_required()
        from app.database import engine, verify_db_schema

        verify_db_schema(engine)
    logger.info("inventory-desk starting (env=%s)", settings.app_env)
    yield
    logger.info("inventory-desk shutting down")


app = FastAPI(
    title="Inventory Desk",
    version="0.1.0",
    description="Warehouse inventory REST API — categories, products, atomic stock movements.",
    lifespan=lifespan,
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Log {method, path, status, latency_ms} per request (NFR-8)."""
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    logger.info(
        "%s %s -> %s (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Liveness probe (FR-1)."""
    return {"status": "ok", "service": settings.service_name}


app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(products.router)
