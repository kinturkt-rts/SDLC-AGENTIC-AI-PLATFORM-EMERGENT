"""Tests for GET /health."""


def test_health_ok(client):
    """Health endpoint returns status ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["checks"]["api"] == "ok"
    assert data["checks"]["database"] == "ok"
    assert "version" in data
