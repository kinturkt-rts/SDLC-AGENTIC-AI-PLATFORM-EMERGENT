"""Shared FastAPI dependencies — API-key auth, DB session, role guards.

Standard, FIXED auth module for api-key apps. Copied verbatim onto every
api-key-mode app as app/dependencies.py; write-guard protected
(_VERBATIM_SCAFFOLD_SUFFIXES in developer_agent.py) — the LLM must never edit,
replace, or re-derive this file, and must never create a second file (e.g.
app/auth.py) that reads any other auth header. This is the ONLY place in an
api-key app that is allowed to read a request header for authentication.

Hardcoded, non-negotiable design (do not vary per app):
  - Exactly one auth header: X-API-Key. There is no X-User-Id, no
    X-Admin-Key, no second header of any kind.
  - The header value is a per-user opaque token (e.g. "tok_alice"), never a
    single shared secret. Identity and role are resolved by looking the token
    up in the `users` table (token column, unique) — see
    database-agent's users.token / users.role requirement.
  - require_api_key resolves the caller to a {"user_id", "role"} dict
    (CurrentUser) — the same shape app/dependencies.py's JWT variant exposes
    (get_current_user), so routes gate on current_user["role"] identically
    regardless of auth mode.
  - require_role(*allowed_roles) is provided here, in the SAME fixed file, so
    routes never invent their own role-check mechanism.

require_api_key is declared via APIKeyHeader (fastapi.security), not a bare
Header() param, specifically so FastAPI publishes "X-API-Key" — and only
X-API-Key — in the generated openapi.json's components.securitySchemes. The
frontend and the auth_mode_files/no_invented_auth_headers validation gates
both read the header name from there. A route or file that reads any other
header for auth purposes (bare Header(alias="X-...") or a second
APIKeyHeader(...)) is a hard-fail: see
validate_no_invented_auth_headers in developer_agent.py.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.database import get_db

# ── DB session shorthand ─────────────────────────────────────────────────────
DbSession = Annotated[Session, Depends(get_db)]


# ── API Key Auth (per-user opaque token, looked up in users.token) ──────────

# auto_error=False so a missing header returns None here (not a 422 the security
# scheme would otherwise raise before this function's own 401 check runs).
_api_key_scheme = APIKeyHeader(name="X-API-Key", scheme_name="ApiKeyAuth", auto_error=False)


def require_api_key(
    x_api_key: str | None = Security(_api_key_scheme),
    db: Session = Depends(get_db),
) -> dict:
    """Resolve X-API-Key to the owning user's identity and role.

    Raises HTTPException(401) if the header is missing or matches no user's
    token. Returns {"user_id": <str>, "role": <str>} — never the raw token.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    from app.models.user import User

    user = db.query(User).filter(User.token == x_api_key).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return {"user_id": str(user.id), "role": user.role}


CurrentUser = Annotated[dict, Depends(require_api_key)]


def require_role(*allowed_roles: str):
    """Factory: returns a dependency that checks the resolved user's role.

    Same signature/behavior as the JWT variant's require_role — routes use
    this, never a hand-rolled role check, and never a different header.
    """

    def _checker(current_user: CurrentUser) -> dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
            )
        return current_user

    return _checker
