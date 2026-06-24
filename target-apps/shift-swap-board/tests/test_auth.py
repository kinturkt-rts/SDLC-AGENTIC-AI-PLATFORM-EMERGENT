"""Tests for POST /auth/login."""


def test_login_success(client, seeded):
    resp = client.post("/auth/login", json={"username": "admin", "password": "Password1!"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_password(client, seeded):
    resp = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_user(client, seeded):
    resp = client.post("/auth/login", json={"username": "nobody", "password": "pass"})
    assert resp.status_code == 401


def test_protected_route_no_token(client, seeded):
    resp = client.get("/roster")
    assert resp.status_code == 401
