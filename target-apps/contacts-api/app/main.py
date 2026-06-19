"""FastAPI application entrypoint for contacts-api."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import contacts, departments, health
from app.startup_checks import validate_runtime_config


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application lifespan — startup/shutdown hooks."""
    settings = get_settings()
    validate_runtime_config(settings)
    yield


app = FastAPI(
    title="Contact Directory API",
    description="Internal contact directory service — Pattern B Postgres CRUD.",
    version="1.0.0",
    lifespan=lifespan,
)

# Global exception handler for development
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return detailed errors in development, generic in production."""
    settings = get_settings()
    if settings.app_env == "development":
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "type": exc.__class__.__name__
            }
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Register routers
app.include_router(health.router, tags=["health"])
app.include_router(departments.router, prefix="/departments", tags=["departments"])
app.include_router(contacts.router, prefix="/contacts", tags=["contacts"])