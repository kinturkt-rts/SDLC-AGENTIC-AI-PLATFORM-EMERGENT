"""Tests for GET /health."""


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["checks"]["api"] == "ok"
    assert data["checks"]["database"] == "ok"


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "bug-deduper"
    assert data["status"] == "ok"
