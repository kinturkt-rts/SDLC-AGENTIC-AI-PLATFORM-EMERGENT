"""Auth endpoint tests."""


def test_login_success(client, seed_users):
    resp = client.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "pass123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["role"] == "employee"


def test_login_invalid_credentials(client, seed_users):
    resp = client.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


def test_login_nonexistent_user(client, seed_users):
    resp = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "pass"})
    assert resp.status_code == 401
