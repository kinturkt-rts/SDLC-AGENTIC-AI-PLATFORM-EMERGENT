"""Health endpoint tests."""


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["checks"]["api"] == "ok"
    assert data["checks"]["database"] == "ok"
