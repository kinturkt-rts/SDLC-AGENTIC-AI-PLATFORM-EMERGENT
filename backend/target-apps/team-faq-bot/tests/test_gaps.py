"""Tests for GET /api/v1/gaps."""


def test_gaps_no_auth(client):
    """401 without admin API key."""
    response = client.get("/api/v1/gaps")
    assert response.status_code == 401


def test_gaps_user_key_rejected(client, api_headers):
    """401 with user API key (not admin)."""
    response = client.get("/api/v1/gaps", headers=api_headers)
    assert response.status_code == 401


def test_gaps_returns_not_in_faq_only(client, admin_headers, seed_question_logs):
    """Returns only 'not_in_faq' entries."""
    response = client.get("/api/v1/gaps", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    # Seed has 2 not_in_faq entries
    assert len(data) == 2
    for item in data:
        assert "question_text" in item
        assert "logged_at" in item


def test_gaps_date_filter(client, admin_headers, seed_question_logs):
    """Filter by date range."""
    response = client.get(
        "/api/v1/gaps?from=2024-02-04&to=2024-02-04",
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "architecture" in data[0]["question_text"].lower()
