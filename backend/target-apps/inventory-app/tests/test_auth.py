"""Auth login tests (FR-2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config import settings


def test_admin_login_success(client, seeded):
    """Correct admin credentials yield a bearer token with role=admin."""
    r = client.post("/auth/login", json={"username": "admin", "password": "Admin123!"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == "admin"
    assert body["expires_in"] > 0
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_staff_login_success(client, seeded):
    r = client.post("/auth/login", json={"username": "staff", "password": "Staff123!"})
    assert r.status_code == 200
    assert r.json()["role"] == "staff"


def test_login_wrong_password_returns_401(client, seeded):
    r = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user_returns_401(client, seeded):
    r = client.post("/auth/login", json={"username": "ghost", "password": "x"})
    assert r.status_code == 401


def test_login_inactive_user_returns_401(client, seeded):
    """is_active=false users cannot obtain a token (FR-2)."""
    r = client.post("/auth/login", json={"username": "inactive", "password": "Inactive123!"})
    assert r.status_code == 401


def test_protected_route_401_without_token(client, seeded):
    r = client.get("/categories")
    assert r.status_code == 401


def test_protected_route_401_with_expired_token(client, seeded):
    """Expired JWT must be rejected with 401, not 200 (FR-3)."""
    expired = jwt.encode(
        {
            "sub": str(seeded["admin_id"]),
            "role": "admin",
            "iat": int((datetime.now(tz=timezone.utc) - timedelta(hours=2)).timestamp()),
            "exp": int((datetime.now(tz=timezone.utc) - timedelta(hours=1)).timestamp()),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    r = client.get("/categories", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


def test_protected_route_401_with_garbage_token(client, seeded):
    r = client.get("/categories", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401
