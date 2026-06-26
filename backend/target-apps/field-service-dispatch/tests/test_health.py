"""Tests for GET /health endpoint."""


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["checks"]["api"] == "ok"
    assert data["checks"]["database"] == "ok"
