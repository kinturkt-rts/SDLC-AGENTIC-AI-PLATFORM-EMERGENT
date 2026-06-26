"""Health check router."""
from fastapi import APIRouter, HTTPException

from app.database import ping_database

router = APIRouter()


@router.get("/health")
def health_check():
    """Health check that validates database connectivity."""
    db_ok = ping_database()
    if not db_ok:
        raise HTTPException(status_code=503, detail="Database connection failed")
    return {
        "status": "ok",
        "checks": {
            "api": "ok",
            "database": "ok",
        },
    }
