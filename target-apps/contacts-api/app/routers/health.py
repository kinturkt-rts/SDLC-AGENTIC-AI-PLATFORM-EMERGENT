"""Health check endpoint — no auth required."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict:
    return {"status": "ok", "service": "contacts-api"}
