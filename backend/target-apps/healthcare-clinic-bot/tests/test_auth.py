"""Tests for auth endpoint."""


def test_login_invalid_credentials(client):
    response = client.post("/auth/login", json={"username": "nobody", "password": "wrong"})
    assert response.status_code == 401


def test_login_success(client, staff_user):
    response = client.post(
        "/auth/login",
        json={"username": "teststaff", "password": "TestPass123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
