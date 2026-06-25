"""Health endpoint tests."""


def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["checks"]["api"] == "ok"
    assert data["checks"]["database"] == "ok"
    assert data["status"] in ("ok", "degraded")
