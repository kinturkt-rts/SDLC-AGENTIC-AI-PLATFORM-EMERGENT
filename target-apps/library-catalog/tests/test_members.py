import pytest
from fastapi.testclient import TestClient


def test_create_member_success(client: TestClient, librarian_headers):
    """Test successful member creation."""
    member_data = {
        "email": "newmember@company.com",
        "name": "New Member"
    }
    
    response = client.post("/members/", json=member_data, headers=librarian_headers)
    assert response.status_code == 201
    data = response.json()
    
    assert data["email"] == "newmember@company.com"
    assert data["name"] == "New Member"
    assert "id" in data
    assert "member_key" in data
    assert data["member_key"].startswith("MBR_")


def test_create_member_without_auth_fails(client: TestClient):
    """Test creating member without auth fails."""
    member_data = {
        "email": "unauthorized@company.com",
        "name": "Unauthorized User"
    }
    
    response = client.post("/members/", json=member_data)
    assert response.status_code == 401


def test_create_duplicate_email_fails(client: TestClient, librarian_headers, sample_member):
    """Test creating member with duplicate email fails."""
    member_data = {
        "email": sample_member.email,  # Same email as sample_member
        "name": "Different Name"
    }
    
    response = client.post("/members/", json=member_data, headers=librarian_headers)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]