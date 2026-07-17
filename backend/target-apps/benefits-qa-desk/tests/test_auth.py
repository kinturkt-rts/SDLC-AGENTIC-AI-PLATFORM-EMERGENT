"""Auth endpoint tests."""
import uuid

from app.models.user import User
from app.security import hash_password


def test_login_success(client, db_session):
    pw = hash_password("GoodPass1!")
    user = User(
        id=str(uuid.uuid4()),
        username="loginuser",
        hashed_password=pw,
        role="employee",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    resp = client.post("/auth/token", json={"username": "loginuser", "password": "GoodPass1!"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "employee"


def test_login_bad_password(client, db_session):
    pw = hash_password("GoodPass1!")
    user = User(
        id=str(uuid.uuid4()),
        username="badlogin",
        hashed_password=pw,
        role="employee",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    resp = client.post("/auth/token", json={"username": "badlogin", "password": "WrongPass"})
    assert resp.status_code == 401


def test_login_inactive_user(client, db_session):
    pw = hash_password("GoodPass1!")
    user = User(
        id=str(uuid.uuid4()),
        username="inactive",
        hashed_password=pw,
        role="employee",
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    resp = client.post("/auth/token", json={"username": "inactive", "password": "GoodPass1!"})
    assert resp.status_code == 401


def test_protected_endpoint_no_token(client):
    resp = client.get("/api/v1/collections")
    assert resp.status_code == 401
