"""Health endpoint — real DB ping."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status

from app.startup_checks import ping_database

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
def health(response: Response) -> dict:
    """Liveness + DB ping. Returns 503 when the database is unreachable."""
    checks: dict[str, str] = {"api": "ok"}
    try:
        ping_database()
        checks["database"] = "ok"
    except Exception as exc:
        logger.exception("health_db_failed")
        checks["database"] = f"error: {exc.__class__.__name__}"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}
