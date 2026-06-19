"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.startup_checks import validate_runtime_config
from app.routers import health, zones, desks, bookings, availability, blackouts


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()
    if not settings.skip_startup_checks:
        validate_runtime_config(settings)
    yield


app = FastAPI(
    title="Desk Booking API",
    description="Hot desk booking system for hybrid office teams",
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


# Register routers
app.include_router(health.router)
app.include_router(zones.router, prefix="/zones", tags=["zones"])
app.include_router(desks.router, prefix="/desks", tags=["desks"])
app.include_router(bookings.router, prefix="/bookings", tags=["bookings"])
app.include_router(availability.router, prefix="/availability", tags=["availability"])
app.include_router(blackouts.router, prefix="/blackouts", tags=["blackouts"])
