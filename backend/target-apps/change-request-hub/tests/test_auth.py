"""Auth endpoint tests."""


def test_login_success(client, seed_users):
    resp = client.post("/api/v1/auth/token", json={"email": "manager@test.com", "password": "TestPass123!"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, seed_users):
    resp = client.post("/api/v1/auth/token", json={"email": "manager@test.com", "password": "wrong"})
    assert resp.status_code == 401


def test_login_nonexistent_user(client, seed_users):
    resp = client.post("/api/v1/auth/token", json={"email": "nobody@test.com", "password": "pass"})
    assert resp.status_code == 401


def test_protected_route_no_token(client):
    resp = client.get("/api/v1/services")
    assert resp.status_code == 401


def test_protected_route_invalid_token(client):
    resp = client.get("/api/v1/services", headers={"Authorization": "Bearer bad.token.here"})
    assert resp.status_code == 401
