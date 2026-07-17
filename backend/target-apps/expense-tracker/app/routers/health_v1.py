"""Health v1 endpoint at /api/v1/health."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status

from app.startup_checks import ping_database

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/api/v1/health")
def health_v1(response: Response) -> dict:
    """Liveness + DB ping at versioned path. Returns 503 when the database is unreachable."""
    checks: dict[str, str] = {"api": "ok"}
    try:
        ping_database()
        checks["database"] = "ok"
    except Exception as exc:
        logger.exception("health_db_failed")
        checks["database"] = f"error: {exc.__class__.__name__}"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    db_ok = checks.get("database") == "ok"
    overall = "ok" if db_ok else "degraded"
    return {"status": overall, "checks": checks}
