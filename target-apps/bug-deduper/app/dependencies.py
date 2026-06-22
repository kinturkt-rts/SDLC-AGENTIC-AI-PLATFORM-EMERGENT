"""FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    settings = get_settings()
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


def require_admin_key(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> str:
    settings = get_settings()
    if not x_admin_key or x_admin_key != settings.admin_key:
        raise HTTPException(status_code=403, detail="Invalid or missing admin key")
    return x_admin_key


DbSession = Annotated[Session, Depends(get_db)]
ApiKeyDep = Annotated[str, Depends(require_api_key)]
AdminKeyDep = Annotated[str, Depends(require_admin_key)]
