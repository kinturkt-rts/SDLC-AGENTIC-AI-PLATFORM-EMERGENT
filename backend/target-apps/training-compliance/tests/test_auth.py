"""Auth endpoint tests."""


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_login_success(client, seed_data):
    resp = client.post("/auth/token", json={"email": "hr@example.com", "password": "Test123!"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_password(client, seed_data):
    resp = client.post("/auth/token", json={"email": "hr@example.com", "password": "wrong"})
    assert resp.status_code == 401


def test_login_nonexistent_user(client, seed_data):
    resp = client.post("/auth/token", json={"email": "nobody@example.com", "password": "Test123!"})
    assert resp.status_code == 401


def test_protected_endpoint_no_token(client, seed_data):
    resp = client.get("/courses")
    assert resp.status_code == 401
