"""Shared FastAPI dependencies — auth, DB session, RBAC.

Replace the stub implementations with real logic once the auth provider
(Cognito / Azure AD / custom JWT) is confirmed in design §5.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db

_bearer = HTTPBearer(auto_error=True)

# ── DB session shorthand ─────────────────────────────────────────────────────

DbSession = Annotated[Session, Depends(get_db)]


# ── Auth ─────────────────────────────────────────────────────────────────────

class CurrentUser:
    """Minimal token-derived user context injected by the auth dependency."""

    def __init__(self, user_id: str, email: str, role: str) -> None:
        self.user_id = user_id
        self.email = email
        self.role = role


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> CurrentUser:
    """Validate JWT bearer token and return the requesting user.

    Replace this stub with real JWT validation (PyJWT / python-jose) using
    the public key / secret from config.settings.jwt_secret_key and the
    claim mapping described in design §5.
    """
    # TODO: implement JWT decode + DB lookup for design §5 auth rules
    token = credentials.credentials  # noqa: F841
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="JWT validation not yet implemented — see app/dependencies.py",
    )


AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
