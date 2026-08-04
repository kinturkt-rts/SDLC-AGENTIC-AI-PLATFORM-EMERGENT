"""Current-user endpoint — resolves the caller's identity and role from X-API-Key."""
from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import CurrentUser

router = APIRouter(tags=["users"])


@router.get("/api/v1/users/me")
def get_me(current_user: CurrentUser) -> dict:
    """Return the authenticated caller's id and role, resolved from X-API-Key."""
    return {"id": current_user["user_id"], "role": current_user["role"]}
