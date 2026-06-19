"""FastAPI dependencies for authentication and database sessions."""

from typing import Annotated
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key")
) -> str:
    """Validate API key from X-API-Key header."""
    settings = get_settings()
    
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    
    return x_api_key


# Type aliases for dependency injection
DbSession = Annotated[Session, Depends(get_db)]
ApiKeyDep = Annotated[str, Depends(require_api_key)]