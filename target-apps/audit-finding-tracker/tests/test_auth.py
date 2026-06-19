"""Tests for authentication endpoints."""

import pytest
from fastapi.testclient import TestClient


def test_login_success(client: TestClient, seeded_users):
    """Test successful login returns JWT token."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "test.auditor@company.com",
            "password": "password"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_at" in data
    assert data["user"]["email"] == "test.auditor@company.com"
    assert data["user"]["role"] == "auditor"


def test_login_invalid_email(client: TestClient, seeded_users):
    """Test login with invalid email returns 401."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@company.com",
            "password": "password"
        }
    )
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_invalid_password(client: TestClient, seeded_users):
    """Test login with invalid password returns 401."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "test.auditor@company.com",
            "password": "wrongpassword"
        }
    )
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_missing_fields(client: TestClient):
    """Test login with missing fields returns 422."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@company.com"}  # Missing password
    )
    
    assert response.status_code == 422