from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.startup_checks import validate_runtime_config
from app.routers import health, books, loans, holds, members


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    if not settings.skip_startup_checks:
        validate_runtime_config(settings)
    yield


app = FastAPI(
    title="Library Catalog API",
    description="Corporate library book borrowing system with date-aware loan management and FIFO hold queues",
    version="1.0.0",
    lifespan=lifespan
)


# Exception handler for development
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    settings = get_settings()
    if settings.app_env == "development":
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": exc.__class__.__name__}
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Include routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(books.router, prefix="/books", tags=["books"])
app.include_router(loans.router, prefix="/loans", tags=["loans"])
app.include_router(holds.router, prefix="/holds", tags=["holds"])
app.include_router(members.router, prefix="/members", tags=["members"])