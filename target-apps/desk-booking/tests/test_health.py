"""Health endpoint tests."""


def test_health_check(client):
    """GET /health returns 200 with db check."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["checks"]["api"] == "ok"
    assert data["checks"]["database"] == "ok"
