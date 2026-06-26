"""Tests for audit endpoints."""

import pytest
from fastapi.testclient import TestClient


def test_list_audits_success(client: TestClient, auth_headers, seeded_users):
    """Test successful audit list retrieval."""
    headers = auth_headers("auditor")
    
    response = client.get("/api/v1/audits/", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    assert "audits" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert isinstance(data["audits"], list)


def test_list_audits_with_status_filter(client: TestClient, auth_headers, seeded_users):
    """Test audit list with status filtering."""
    headers = auth_headers("auditor")
    
    response = client.get("/api/v1/audits/?status=active", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    # All returned audits should have active status
    for audit in data["audits"]:
        assert audit["status"] == "active"


def test_list_audits_unauthorized(client: TestClient):
    """Test audit list without auth returns 401."""
    response = client.get("/api/v1/audits/")
    
    assert response.status_code == 401


def test_list_audits_assignee_forbidden(client: TestClient, auth_headers, seeded_users):
    """Test assignee role cannot access audits."""
    headers = auth_headers("assignee")
    
    response = client.get("/api/v1/audits/", headers=headers)
    
    assert response.status_code == 403
    assert response.json()["detail"] == "Auditor or executive access required"


def test_create_audit_success(client: TestClient, auth_headers, seeded_users):
    """Test successful audit creation."""
    headers = auth_headers("auditor")
    
    response = client.post(
        "/api/v1/audits/",
        headers=headers,
        json={
            "title": "Test Audit",
            "description": "A test audit description"
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["title"] == "Test Audit"
    assert data["description"] == "A test audit description"
    assert data["status"] == "planning"
    assert data["version"] == 1
    assert "id" in data
    assert "created_at" in data


def test_create_audit_unauthorized(client: TestClient):
    """Test audit creation without auth returns 401."""
    response = client.post(
        "/api/v1/audits/",
        json={
            "title": "Test Audit",
            "description": "A test audit description"
        }
    )
    
    assert response.status_code == 401


def test_create_audit_assignee_forbidden(client: TestClient, auth_headers, seeded_users):
    """Test assignee role cannot create audits."""
    headers = auth_headers("assignee")
    
    response = client.post(
        "/api/v1/audits/",
        headers=headers,
        json={
            "title": "Test Audit", 
            "description": "A test audit description"
        }
    )
    
    assert response.status_code == 403