"""FastAPI application — Healthcare Clinic Assistant."""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import admin, auth, chat, faqs, health

# Structured logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}',
    stream=sys.stdout,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks."""
    logging.getLogger(__name__).info("Healthcare Clinic Assistant starting up")
    yield
    logging.getLogger(__name__).info("Healthcare Clinic Assistant shutting down")


app = FastAPI(
    title="Healthcare Clinic Assistant API",
    description="FAQ chatbot backend for a healthcare clinic demo.",
    version="1.0.0",
    lifespan=lifespan,
)

# Register routers
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(faqs.router, prefix="/faqs", tags=["faqs"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
