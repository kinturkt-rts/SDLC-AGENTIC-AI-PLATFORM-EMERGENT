"""Main FastAPI application for PR Diff Summarizer."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.startup_checks import validate_runtime_config
from app.routers import health, reviews, stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with startup validation."""
    # Startup: validate configuration
    settings = get_settings()
    validate_runtime_config(settings)
    yield


app = FastAPI(
    title="PR Diff Summarizer API",
    description="AI-powered PR diff analysis and risk scoring service",
    version="1.0.0",
    lifespan=lifespan
)

# Global exception handler for development
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions with detailed error info in development."""
    settings = get_settings()
    if settings.app_env == "development":
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "type": exc.__class__.__name__
            }
        )
    # Production: generic error message
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Register routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
app.include_router(stats.router, prefix="/stats", tags=["stats"])