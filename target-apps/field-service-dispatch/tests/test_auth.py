"""Tests for auth router."""


def test_login_success(client, seed_users):
    resp = client.post(
        "/auth/token",
        data={"username": "dispatcher1", "password": "Test123!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "dispatcher"


def test_login_invalid_password(client, seed_users):
    resp = client.post(
        "/auth/token",
        data={"username": "dispatcher1", "password": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


def test_login_unknown_user(client, seed_users):
    resp = client.post(
        "/auth/token",
        data={"username": "nobody", "password": "Test123!"},
    )
    assert resp.status_code == 401


def test_protected_route_no_token(client):
    resp = client.get("/technicians")
    assert resp.status_code == 401
