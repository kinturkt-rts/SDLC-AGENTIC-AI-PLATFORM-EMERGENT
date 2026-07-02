"""Tests for health endpoint."""


def test_health_returns_ok(client, mock_bedrock_for_health):
    """GET /health returns status ok with db and bedrock_client."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "ok"
    assert data["bedrock_client"] == "ok"


def test_health_no_auth_required(client, mock_bedrock_for_health):
    """GET /health should not require API key."""
    response = client.get("/health")
    assert response.status_code == 200
