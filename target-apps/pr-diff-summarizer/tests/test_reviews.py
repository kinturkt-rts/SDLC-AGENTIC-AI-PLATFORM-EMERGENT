"""Tests for review endpoints."""

import json
from fastapi.testclient import TestClient


def test_create_review_success(client: TestClient, api_headers: dict, mock_bedrock):
    """Test successful review creation."""
    payload = {
        "title": "Add authentication middleware",
        "diff_text": "diff --git a/auth.py b/auth.py\n+def authenticate():\n+    pass"
    }
    
    response = client.post("/reviews/", json=payload, headers=api_headers)
    assert response.status_code == 201
    
    data = response.json()
    assert "id" in data
    assert data["title"] == payload["title"]
    assert data["summary"] == "Test AI summary of diff changes"
    assert data["risk_score"] == 45
    assert data["risk_band"] == "medium"
    assert data["file_count"] >= 0
    assert data["lines_added"] >= 0
    assert data["lines_removed"] >= 0
    
    # Verify Bedrock was called
    mock_bedrock.invoke_text.assert_called_once()


def test_create_review_missing_auth(client: TestClient):
    """Test create review without API key."""
    payload = {
        "title": "Test PR",
        "diff_text": "diff --git a/test.py"
    }
    
    response = client.post("/reviews/", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key"


def test_create_review_invalid_auth(client: TestClient):
    """Test create review with invalid API key."""
    payload = {
        "title": "Test PR", 
        "diff_text": "diff --git a/test.py"
    }
    headers = {"X-API-Key": "invalid-key"}
    
    response = client.post("/reviews/", json=payload, headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key"


def test_list_reviews_empty(client: TestClient, api_headers: dict):
    """Test list reviews with no data."""
    response = client.get("/reviews/", headers=api_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["limit"] == 20
    assert data["offset"] == 0


def test_list_reviews_with_data(client: TestClient, api_headers: dict, seeded_review):
    """Test list reviews with seeded data."""
    response = client.get("/reviews/", headers=api_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["items"]) == 1
    assert data["total"] == 1
    assert data["items"][0]["id"] == seeded_review.id
    assert data["items"][0]["title"] == seeded_review.title


def test_list_reviews_pagination(client: TestClient, api_headers: dict, seeded_review):
    """Test list reviews with pagination."""
    response = client.get("/reviews/?limit=1&offset=0", headers=api_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert data["limit"] == 1
    assert data["offset"] == 0
    assert len(data["items"]) <= 1


def test_list_reviews_risk_band_filter(client: TestClient, api_headers: dict, seeded_review):
    """Test list reviews filtered by risk band."""
    # Filter by LOW risk band (matching seeded review)
    response = client.get("/reviews/?risk_band=low", headers=api_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["risk_band"] == "low"
    
    # Filter by HIGH risk band (should be empty)
    response = client.get("/reviews/?risk_band=high", headers=api_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["items"]) == 0


def test_list_reviews_invalid_risk_band(client: TestClient, api_headers: dict):
    """Test list reviews with invalid risk band filter."""
    response = client.get("/reviews/?risk_band=invalid", headers=api_headers)
    assert response.status_code == 400
    assert "Invalid risk_band" in response.json()["detail"]


def test_get_review_success(client: TestClient, api_headers: dict, seeded_review):
    """Test get specific review by ID."""
    response = client.get(f"/reviews/{seeded_review.id}", headers=api_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == seeded_review.id
    assert data["title"] == seeded_review.title
    assert data["summary"] == seeded_review.summary
    assert data["risk_score"] == seeded_review.risk_score


def test_get_review_not_found(client: TestClient, api_headers: dict):
    """Test get review with non-existent ID."""
    response = client.get("/reviews/00000000-0000-0000-0000-000000000000", headers=api_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Review not found"


def test_get_review_missing_auth(client: TestClient, seeded_review):
    """Test get review without API key."""
    response = client.get(f"/reviews/{seeded_review.id}")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key"