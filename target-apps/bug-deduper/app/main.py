"""Bug deduplicator API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import bugs, health
from app.startup_checks import validate_runtime_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_runtime_config(get_settings())
    yield


app = FastAPI(
    title="Bug Deduper API",
    description="Find semantically similar bugs when filing new reports",
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
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(bugs.router, prefix="/bugs", tags=["bugs"])
