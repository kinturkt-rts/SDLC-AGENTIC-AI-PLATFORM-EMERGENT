"""Health endpoint test (FR-1)."""

from __future__ import annotations


def test_health_no_auth_required(client):
    """GET /health returns 200 with the documented body and no auth."""
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "service" in body
