"""Tests for POST /auth/token."""


def test_login_success(client, seed_users):
    """Valid credentials return access_token and role."""
    resp = client.post("/auth/token", json={
        "email": "priya@example.com",
        "password": "KnowledgeHub2024!",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["role"] == "knowledge_admin"


def test_login_invalid_password(client, seed_users):
    """Invalid password returns 401."""
    resp = client.post("/auth/token", json={
        "email": "priya@example.com",
        "password": "wrong-password",
    })
    assert resp.status_code == 401


def test_login_unknown_email(client, seed_users):
    """Unknown email returns 401."""
    resp = client.post("/auth/token", json={
        "email": "nobody@example.com",
        "password": "KnowledgeHub2024!",
    })
    assert resp.status_code == 401
