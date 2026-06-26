"""Health endpoint tests."""


def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["checks"]["database"] == "ok"


def test_health_no_auth_required(client):
    """Health does NOT require auth."""
    resp = client.get("/health")
    assert resp.status_code == 200
