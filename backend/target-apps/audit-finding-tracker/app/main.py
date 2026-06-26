"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.startup_checks import validate_runtime_config
from app.routers import health, auth, audits, findings, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Startup
    settings = get_settings()
    validate_runtime_config(settings)
    
    # Create upload directory if using local file storage
    if settings.file_storage_type == "local":
        upload_dir = Path(settings.local_upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
    
    yield
    # Shutdown (cleanup if needed)


app = FastAPI(
    title="Audit Finding Tracker API",
    description="Internal audit system for managing SOC findings with centralized workflow and executive reporting",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8501"],  # React/Streamlit dev
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)

# Unhandled errors only — do not catch HTTPException (401/404 etc. from routes).
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Return detailed errors in development, generic in production."""
    if isinstance(exc, HTTPException):
        raise exc
    settings = get_settings()
    if settings.app_env == "development":
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": exc.__class__.__name__},
        )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# Register routers
app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(audits.router, prefix="/api/v1/audits", tags=["audits"])
app.include_router(findings.router, prefix="/api/v1/findings", tags=["findings"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])