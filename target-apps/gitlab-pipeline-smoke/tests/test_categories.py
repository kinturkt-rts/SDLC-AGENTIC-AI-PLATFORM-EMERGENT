"""Tests for category management endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_list_categories_empty(client: TestClient):
    """Test listing categories when none exist."""
    response = client.get("/api/v1/categories/")
    assert response.status_code == 200
    assert response.json() == []


def test_create_category(client: TestClient, api_headers: dict[str, str]):
    """Test creating a category with API key."""
    category_data = {
        "name": "Engineering",
        "description": "Technical updates and announcements",
    }
    
    response = client.post("/api/v1/categories/", json=category_data, headers=api_headers)
    assert response.status_code == 201
    
    data = response.json()
    assert data["name"] == "Engineering"
    assert data["description"] == "Technical updates and announcements"
    assert "id" in data
    assert "created_at" in data


def test_create_category_no_auth(client: TestClient):
    """Test creating a category without API key returns 401."""
    category_data = {
        "name": "Engineering",
        "description": "Technical updates and announcements",
    }
    
    response = client.post("/api/v1/categories/", json=category_data)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key"


def test_create_duplicate_category(client: TestClient, api_headers: dict[str, str]):
    """Test creating duplicate category name returns 409."""
    category_data = {
        "name": "Engineering",
        "description": "Technical updates",
    }
    
    # Create first category
    response = client.post("/api/v1/categories/", json=category_data, headers=api_headers)
    assert response.status_code == 201
    
    # Try to create duplicate
    response = client.post("/api/v1/categories/", json=category_data, headers=api_headers)
    assert response.status_code == 409
    assert "Engineering" in response.json()["detail"]
    assert "already exists" in response.json()["detail"]


def test_list_categories_with_data(client: TestClient, api_headers: dict[str, str]):
    """Test listing categories after creating some."""
    categories = [
        {"name": "General", "description": "General announcements"},
        {"name": "HR", "description": "Human resources updates"},
    ]
    
    # Create categories
    for cat in categories:
        response = client.post("/api/v1/categories/", json=cat, headers=api_headers)
        assert response.status_code == 201
    
    # List all categories
    response = client.get("/api/v1/categories/")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 2
    # Should be ordered by name
    assert data[0]["name"] == "General"
    assert data[1]["name"] == "HR"


def test_get_category_by_id(client: TestClient, api_headers: dict[str, str]):
    """Test getting category by ID."""
    category_data = {
        "name": "Engineering",
        "description": "Technical updates",
    }
    
    # Create category
    response = client.post("/api/v1/categories/", json=category_data, headers=api_headers)
    assert response.status_code == 201
    category_id = response.json()["id"]
    
    # Get by ID
    response = client.get(f"/api/v1/categories/{category_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == category_id
    assert data["name"] == "Engineering"


def test_get_category_not_found(client: TestClient):
    """Test getting non-existent category returns 404."""
    response = client.get("/api/v1/categories/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["detail"] == "Category not found"


def test_update_category(client: TestClient, api_headers: dict[str, str]):
    """Test updating category with API key."""
    # Create category
    category_data = {
        "name": "Engineering",
        "description": "Technical updates",
    }
    response = client.post("/api/v1/categories/", json=category_data, headers=api_headers)
    assert response.status_code == 201
    category_id = response.json()["id"]
    
    # Update category
    update_data = {
        "name": "Engineering Team",
        "description": "Engineering team updates and wins",
    }
    response = client.patch(f"/api/v1/categories/{category_id}", json=update_data, headers=api_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert data["name"] == "Engineering Team"
    assert data["description"] == "Engineering team updates and wins"


def test_update_category_no_auth(client: TestClient, api_headers: dict[str, str]):
    """Test updating category without API key returns 401."""
    # Create category
    category_data = {
        "name": "Engineering",
        "description": "Technical updates",
    }
    response = client.post("/api/v1/categories/", json=category_data, headers=api_headers)
    assert response.status_code == 201
    category_id = response.json()["id"]
    
    # Try to update without auth
    update_data = {"name": "Updated Name"}
    response = client.patch(f"/api/v1/categories/{category_id}", json=update_data)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key"