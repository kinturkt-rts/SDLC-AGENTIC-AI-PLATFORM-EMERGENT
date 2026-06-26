"""Auth endpoint tests."""


def test_login_success(client, seeded_users):
    resp = client.post("/auth/login", json={"username": "test_admin", "password": "Admin123!"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["role"] == "it_admin"


def test_login_invalid_password(client, seeded_users):
    resp = client.post("/auth/login", json={"username": "test_admin", "password": "wrong"})
    assert resp.status_code == 401


def test_login_nonexistent_user(client, seeded_users):
    resp = client.post("/auth/login", json={"username": "ghost", "password": "pass"})
    assert resp.status_code == 401
