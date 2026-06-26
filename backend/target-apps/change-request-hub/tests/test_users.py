"""User list tests."""


def test_list_users(client, manager_headers):
    resp = client.get("/api/v1/users", headers=manager_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 1


def test_list_users_filter_role(client, manager_headers):
    resp = client.get("/api/v1/users?role=implementer", headers=manager_headers)
    assert resp.status_code == 200
    for u in resp.json()["items"]:
        assert u["role"] == "implementer"


def test_list_users_unauthenticated(client):
    resp = client.get("/api/v1/users")
    assert resp.status_code == 401
