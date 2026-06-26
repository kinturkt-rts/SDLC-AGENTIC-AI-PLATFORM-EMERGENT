import pytest
from app.models.user import User
from app.models.pg_types import UserRole, UserStatus
from app.services.auth import hash_password


def test_login_success(client, db):
    """Test successful login returns JWT token"""
    # Create test user
    user = User(
        email="test@company.com",
        password_hash=hash_password("testpass123"),
        role=UserRole.admin,
        status=UserStatus.active
    )
    db.add(user)
    db.commit()
    
    response = client.post("/auth/token", json={
        "email": "test@company.com",
        "password": "testpass123"
    })
    
    assert response.status_code == 200
    data = response.json()
    
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data


def test_login_invalid_credentials(client):
    """Test login with invalid credentials returns 401"""
    response = client.post("/auth/token", json={
        "email": "nonexistent@company.com",
        "password": "wrongpassword"
    })
    
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]


def test_get_user_profile(client, admin_user, auth_headers_admin):
    """Test getting current user profile"""
    response = client.get("/auth/me", headers=auth_headers_admin)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == admin_user.id
    assert data["email"] == admin_user.email
    assert data["role"] == admin_user.role.value
    assert "collections" in data


def test_get_user_profile_unauthorized(client):
    """Test getting user profile without token returns 401"""
    response = client.get("/auth/me")
    
    assert response.status_code == 401
    assert "Authorization header required" in response.json()["detail"]
