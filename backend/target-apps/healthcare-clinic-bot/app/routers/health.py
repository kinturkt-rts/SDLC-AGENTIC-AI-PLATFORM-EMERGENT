"""Health check endpoint."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check():
    """Liveness/readiness probe."""
    return {"status": "ok"}
