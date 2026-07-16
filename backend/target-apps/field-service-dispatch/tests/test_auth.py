"""Auth endpoint tests."""
import uuid


def test_login_success(client, seed_data):
    resp = client.post("/api/v1/auth/token", json={
        "username": "dana_dispatch",
        "password": "FieldService2024!"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "dispatcher"
    assert "access_token" in data


def test_login_invalid_password(client, seed_data):
    resp = client.post("/api/v1/auth/token", json={
        "username": "dana_dispatch",
        "password": "wrong"
    })
    assert resp.status_code == 401


def test_login_invalid_user(client, seed_data):
    resp = client.post("/api/v1/auth/token", json={
        "username": "nonexistent",
        "password": "whatever"
    })
    assert resp.status_code == 401
