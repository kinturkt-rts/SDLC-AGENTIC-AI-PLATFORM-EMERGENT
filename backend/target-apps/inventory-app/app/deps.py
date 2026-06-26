"""FastAPI dependencies — JWT bearer auth and role guards (FR-3, NFR-3).

Returns 401 for missing/invalid/expired tokens and 403 for an authenticated
user with insufficient role. Routers compose these via `Depends(...)`.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.security import TokenDecodeError, decode_access_token

logger = logging.getLogger(__name__)

# auto_error=False so we can raise our own 401 with a clear message.
_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Resolve the authenticated user from the bearer token.

    401 paths (FR-3): no header, malformed JWT, expired JWT, unknown user,
    or user marked `is_active=false`.
    """
    if creds is None or not creds.credentials:
        raise _unauthorized("Missing bearer token")

    try:
        claims = decode_access_token(creds.credentials)
    except TokenDecodeError:
        raise _unauthorized("Invalid or expired token") from None

    sub = claims.get("sub")
    if not sub:
        raise _unauthorized("Invalid token payload")

    try:
        user_id = uuid.UUID(sub)
    except (ValueError, TypeError):
        raise _unauthorized("Invalid token subject") from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("User not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed: UserRole):
    """Return a dependency that asserts `current_user.role in allowed` (FR-3).

    Use as `Depends(require_role(UserRole.admin))`. Returns the user so route
    handlers can inspect identity for audit (e.g. `performed_by`).
    """
    allowed_values = {r.value for r in allowed}

    def _checker(user: CurrentUser) -> User:
        if user.role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role for this operation",
            )
        return user

    return _checker
