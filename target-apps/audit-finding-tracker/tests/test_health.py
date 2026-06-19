from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    # Must match the template's app/routers/health.py which returns "ok".
    # Changing this string requires changing the route in lockstep — they are
    # one contract, scaffolded together.
    assert response.json()["status"] == "ok"