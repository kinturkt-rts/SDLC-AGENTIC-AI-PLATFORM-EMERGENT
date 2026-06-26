from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_items_returns_one_item() -> None:
    response = client.get("/items")
    assert response.status_code == 200

    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 1

    item = payload[0]
    assert item == {"id": 1, "name": "demo-item"}
