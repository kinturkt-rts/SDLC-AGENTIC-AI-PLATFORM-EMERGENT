"""Tests for reviews endpoints."""
import uuid


SAMPLE_DIFF = (
    "diff --git a/app/main.py b/app/main.py\n"
    "--- a/app/main.py\n"
    "+++ b/app/main.py\n"
    "@@ -1,3 +1,5 @@\n"
    "+import os\n"
    "+import sys\n"
    " from fastapi import FastAPI\n"
    "-app = FastAPI()\n"
    "+app = FastAPI(title='test')\n"
)


def test_create_review_success(client, api_headers, mock_bedrock):
    """POST /reviews creates a review and returns 201."""
    body = {"title": "Test PR", "diff_text": SAMPLE_DIFF}
    response = client.post("/reviews", json=body, headers=api_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test PR"
    assert data["file_count"] == 1
    assert data["lines_added"] == 3
    assert data["lines_removed"] == 1
    assert data["summary"] == "Test summary of the changes."
    assert data["risk_factors"] == ["test-factor"]
    assert "risk_score" in data
    assert "risk_band" in data
    assert data["id"] is not None


def test_create_review_no_auth(client):
    """POST /reviews without API key returns 401."""
    body = {"title": "Test PR", "diff_text": "some diff"}
    response = client.post("/reviews", json=body)
    assert response.status_code == 401


def test_create_review_invalid_key(client):
    """POST /reviews with wrong API key returns 401."""
    body = {"title": "Test PR", "diff_text": "some diff"}
    response = client.post("/reviews", json=body, headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


def test_create_review_diff_too_large(client, api_headers, mock_bedrock):
    """POST /reviews with oversized diff returns 422."""
    large_diff = "x" * 200000
    body = {"title": "Big PR", "diff_text": large_diff}
    response = client.post("/reviews", json=body, headers=api_headers)
    assert response.status_code == 422


def test_list_reviews(client, api_headers, sample_review):
    """GET /reviews returns paginated list."""
    response = client.get("/reviews", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert isinstance(data["items"], list)


def test_list_reviews_with_limit_offset(client, api_headers, sample_review):
    """GET /reviews?limit=10&offset=0 returns paginated results."""
    response = client.get("/reviews?limit=10&offset=0", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


def test_list_reviews_filter_by_band(client, api_headers, sample_review):
    """GET /reviews?risk_band=low returns filtered results."""
    response = client.get("/reviews?risk_band=low", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["risk_band"] == "low"


def test_list_reviews_no_auth(client):
    """GET /reviews without API key returns 401."""
    response = client.get("/reviews")
    assert response.status_code == 401


def test_get_review_by_id(client, api_headers, sample_review):
    """GET /reviews/{id} returns the review."""
    response = client.get(f"/reviews/{sample_review.id}", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(sample_review.id)
    assert data["title"] == sample_review.title


def test_get_review_not_found(client, api_headers):
    """GET /reviews/{id} with non-existent ID returns 404."""
    fake_id = str(uuid.uuid4())
    response = client.get(f"/reviews/{fake_id}", headers=api_headers)
    assert response.status_code == 404
