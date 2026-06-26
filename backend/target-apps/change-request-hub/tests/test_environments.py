"""Environment tests."""


def test_create_environment_manager(client, manager_headers):
    resp = client.post("/api/v1/environments", json={"name": "production", "sort_order": 10}, headers=manager_headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "production"


def test_list_environments(client, manager_headers):
    client.post("/api/v1/environments", json={"name": "staging", "sort_order": 5}, headers=manager_headers)
    resp = client.get("/api/v1/environments", headers=manager_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_create_environment_requester_forbidden(client, requester_headers):
    resp = client.post("/api/v1/environments", json={"name": "dev", "sort_order": 1}, headers=requester_headers)
    assert resp.status_code == 403
