"""Tests for notice management endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient


def test_create_notice(client: TestClient, api_headers: dict[str, str], seed_categories: dict[str, str]):
    """Test creating a notice with API key."""
    notice_data = {
        "category_id": seed_categories["general"],
        "title": "Welcome to Q1",
        "body": "We are starting the new quarter with exciting initiatives.",
        "author_name": "Alice Johnson",
    }
    
    response = client.post("/api/v1/notices/", json=notice_data, headers=api_headers)
    assert response.status_code == 201
    
    data = response.json()
    assert data["title"] == "Welcome to Q1"
    assert data["body"] == "We are starting the new quarter with exciting initiatives."
    assert data["author_name"] == "Alice Johnson"
    assert data["category_id"] == seed_categories["general"]
    assert data["is_archived"] is False
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_notice_no_auth(client: TestClient, seed_categories: dict[str, str]):
    """Test creating a notice without API key returns 401."""
    notice_data = {
        "category_id": seed_categories["general"],
        "title": "Test Notice",
        "body": "Test body",
        "author_name": "Test Author",
    }
    
    response = client.post("/api/v1/notices/", json=notice_data)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key"


def test_create_notice_invalid_category(client: TestClient, api_headers: dict[str, str]):
    """Test creating notice with invalid category returns 404."""
    notice_data = {
        "category_id": "00000000-0000-0000-0000-000000000000",
        "title": "Test Notice",
        "body": "Test body",
        "author_name": "Test Author",
    }
    
    response = client.post("/api/v1/notices/", json=notice_data, headers=api_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Category not found"


def test_create_notice_invalid_date_range(client: TestClient, api_headers: dict[str, str], seed_categories: dict[str, str]):
    """Test creating notice with ends_at < starts_at returns 422."""
    now = datetime.utcnow()
    notice_data = {
        "category_id": seed_categories["general"],
        "title": "Test Notice",
        "body": "Test body",
        "author_name": "Test Author",
        "starts_at": now.isoformat(),
        "ends_at": (now - timedelta(hours=1)).isoformat(),
    }
    
    response = client.post("/api/v1/notices/", json=notice_data, headers=api_headers)
    assert response.status_code == 422
    assert "ends_at must be greater than or equal to starts_at" in response.json()["detail"]


def test_list_notices_empty(client: TestClient):
    """Test listing notices when none exist."""
    response = client.get("/api/v1/notices/")
    assert response.status_code == 200
    
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["limit"] == 20
    assert data["offset"] == 0


def test_list_notices_with_data(client: TestClient, seed_notices: dict[str, str]):
    """Test listing notices with seed data."""
    response = client.get("/api/v1/notices/")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["items"]) > 0
    assert data["total"] > 0
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data


def test_list_notices_active_only_filter(client: TestClient, seed_notices: dict[str, str]):
    """Test active_only filter excludes archived/expired notices."""
    # Test with active_only=true (default)
    response = client.get("/api/v1/notices/?active_only=true")
    assert response.status_code == 200
    
    active_data = response.json()
    
    # Test with active_only=false
    response = client.get("/api/v1/notices/?active_only=false")
    assert response.status_code == 200
    
    all_data = response.json()
    
    # All notices should include archived/expired, so total should be >= active
    assert all_data["total"] >= active_data["total"]


def test_list_notices_pagination(client: TestClient, seed_notices: dict[str, str]):
    """Test pagination parameters."""
    # Test first page
    response = client.get("/api/v1/notices/?limit=2&offset=0")
    assert response.status_code == 200
    
    data = response.json()
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert len(data["items"]) <= 2


def test_list_notices_search(client: TestClient, api_headers: dict[str, str], seed_categories: dict[str, str]):
    """Test search functionality."""
    # Create a notice with unique content
    notice_data = {
        "category_id": seed_categories["general"],
        "title": "Unique search test title",
        "body": "This notice has searchable content for testing",
        "author_name": "Test Author",
    }
    
    response = client.post("/api/v1/notices/", json=notice_data, headers=api_headers)
    assert response.status_code == 201
    
    # Search by title
    response = client.get("/api/v1/notices/?q=unique search")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["items"]) > 0
    assert any("Unique search" in item["title"] for item in data["items"])


def test_get_notice_by_id(client: TestClient, api_headers: dict[str, str], seed_categories: dict[str, str]):
    """Test getting notice by ID."""
    notice_data = {
        "category_id": seed_categories["general"],
        "title": "Test Notice",
        "body": "Test body",
        "author_name": "Test Author",
    }
    
    # Create notice
    response = client.post("/api/v1/notices/", json=notice_data, headers=api_headers)
    assert response.status_code == 201
    notice_id = response.json()["id"]
    
    # Get by ID
    response = client.get(f"/api/v1/notices/{notice_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == notice_id
    assert data["title"] == "Test Notice"


def test_get_notice_not_found(client: TestClient):
    """Test getting non-existent notice returns 404."""
    response = client.get("/api/v1/notices/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["detail"] == "Notice not found"


def test_update_notice(client: TestClient, api_headers: dict[str, str], seed_categories: dict[str, str]):
    """Test updating notice with API key."""
    # Create notice
    notice_data = {
        "category_id": seed_categories["general"],
        "title": "Original Title",
        "body": "Original body",
        "author_name": "Test Author",
    }
    response = client.post("/api/v1/notices/", json=notice_data, headers=api_headers)
    assert response.status_code == 201
    notice_id = response.json()["id"]
    
    # Update notice
    update_data = {
        "title": "Updated Title",
        "body": "Updated body content",
    }
    response = client.patch(f"/api/v1/notices/{notice_id}", json=update_data, headers=api_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["body"] == "Updated body content"


def test_update_notice_no_auth(client: TestClient, seed_notices: dict[str, str]):
    """Test updating notice without API key returns 401."""
    notice_id = list(seed_notices.values())[0]
    
    update_data = {"title": "Updated Title"}
    response = client.patch(f"/api/v1/notices/{notice_id}", json=update_data)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key"


def test_archive_notice(client: TestClient, api_headers: dict[str, str], seed_categories: dict[str, str]):
    """Test archiving notice."""
    # Create notice
    notice_data = {
        "category_id": seed_categories["general"],
        "title": "Test Notice",
        "body": "Test body",
        "author_name": "Test Author",
    }
    response = client.post("/api/v1/notices/", json=notice_data, headers=api_headers)
    assert response.status_code == 201
    notice_id = response.json()["id"]
    
    # Archive notice
    response = client.post(f"/api/v1/notices/{notice_id}/archive", headers=api_headers)
    assert response.status_code == 204
    
    # Verify notice is archived
    response = client.get(f"/api/v1/notices/{notice_id}")
    assert response.status_code == 200
    assert response.json()["is_archived"] is True


def test_archive_notice_idempotent(client: TestClient, api_headers: dict[str, str], seed_categories: dict[str, str]):
    """Test archiving notice is idempotent."""
    # Create notice
    notice_data = {
        "category_id": seed_categories["general"],
        "title": "Test Notice",
        "body": "Test body",
        "author_name": "Test Author",
    }
    response = client.post("/api/v1/notices/", json=notice_data, headers=api_headers)
    assert response.status_code == 201
    notice_id = response.json()["id"]
    
    # Archive notice twice
    response = client.post(f"/api/v1/notices/{notice_id}/archive", headers=api_headers)
    assert response.status_code == 204
    
    response = client.post(f"/api/v1/notices/{notice_id}/archive", headers=api_headers)
    assert response.status_code == 204


def test_archive_notice_no_auth(client: TestClient, seed_notices: dict[str, str]):
    """Test archiving notice without API key returns 401."""
    notice_id = list(seed_notices.values())[0]
    
    response = client.post(f"/api/v1/notices/{notice_id}/archive")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key"