"""Health endpoint tests."""


def test_health_returns_ok(client, api_headers):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["checks"]["api"] == "ok"
    assert data["checks"]["database"] == "ok"
