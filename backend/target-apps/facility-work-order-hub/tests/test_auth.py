"""Test auth endpoints."""
import uuid

from app.models.user import User
from app.security import hash_password


def test_login_success(client, db_session):
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email="login@test.com",
        hashed_password=hash_password("TestPass123!"),
        display_name="Login User",
        role="requester",
    )
    db_session.add(user)
    db_session.commit()

    resp = client.post("/api/v1/auth/token", json={"email": "login@test.com", "password": "TestPass123!"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, db_session):
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email="wrong@test.com",
        hashed_password=hash_password("TestPass123!"),
        display_name="Wrong User",
        role="requester",
    )
    db_session.add(user)
    db_session.commit()

    resp = client.post("/api/v1/auth/token", json={"email": "wrong@test.com", "password": "BadPass"})
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    resp = client.post("/api/v1/auth/token", json={"email": "nope@test.com", "password": "x"})
    assert resp.status_code == 401
