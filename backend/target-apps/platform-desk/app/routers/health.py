"""Health endpoints — real dependency checks, not a fake ok response."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status

from app.config import get_settings
from app.startup_checks import ping_database

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
def health(response: Response) -> dict:
    """Liveness + DB ping. Returns 503 when the database is unreachable."""
    checks: dict[str, str] = {"api": "ok"}
    settings = get_settings()

    try:
        ping_database()
        checks["database"] = "ok"
    except Exception as exc:
        logger.exception("health_db_failed")
        checks["database"] = f"error: {exc.__class__.__name__}"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    # Optional Bedrock probe when the app uses LLM inference
    if getattr(settings, "bedrock_model_id", None) and settings.bedrock_model_id.strip():
        try:
            from app.services.bedrock_client import get_bedrock_client

            client = get_bedrock_client()
            if hasattr(client, "ping"):
                client.ping()
            checks["bedrock"] = "ok"
        except Exception as exc:
            logger.warning("health_bedrock_failed: %s", exc)
            checks["bedrock"] = f"error: {exc.__class__.__name__}"
            if response.status_code < 400:
                response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}
