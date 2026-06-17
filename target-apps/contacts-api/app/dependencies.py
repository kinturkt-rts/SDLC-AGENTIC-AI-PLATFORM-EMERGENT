"""Shared FastAPI dependencies — API-key auth guard."""
import hmac

from fastapi import Header, HTTPException

from app.config import get_settings


def require_api_key(x_api_key: str = Header(alias="X-API-Key", default="")) -> None:
    """Validate X-API-Key header against settings.API_KEY (constant-time compare)."""
    settings = get_settings()
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
