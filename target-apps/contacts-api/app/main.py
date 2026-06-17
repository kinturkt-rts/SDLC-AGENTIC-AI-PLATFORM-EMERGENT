"""FastAPI application entrypoint for contacts-api."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import contacts, departments, health


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application lifespan — startup/shutdown hooks."""
    # Startup: nothing required for MVP (migrations applied externally)
    yield
    # Shutdown: nothing required


app = FastAPI(
    title="Contact Directory API",
    description="Internal contact directory service — Pattern B Postgres CRUD.",
    version="1.0.0",
    lifespan=lifespan,
)

# Register routers
app.include_router(health.router, tags=["health"])
app.include_router(departments.router, prefix="/departments", tags=["departments"])
app.include_router(contacts.router, prefix="/contacts", tags=["contacts"])
