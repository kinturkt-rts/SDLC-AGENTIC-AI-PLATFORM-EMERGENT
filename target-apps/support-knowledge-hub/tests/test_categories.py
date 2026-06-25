"""Category endpoint tests."""


def test_list_categories(client, seed_users, seed_category):
    headers = {"Authorization": f"Bearer {seed_users['employee_token']}"}
    resp = client.get("/api/v1/categories", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "IT"


def test_create_category_admin(client, seed_users):
    headers = {"Authorization": f"Bearer {seed_users['admin_token']}"}
    resp = client.post("/api/v1/categories", json={"name": "Finance"}, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "Finance"


def test_create_category_forbidden_for_contributor(client, seed_users):
    headers = {"Authorization": f"Bearer {seed_users['contributor_token']}"}
    resp = client.post("/api/v1/categories", json={"name": "Illegal"}, headers=headers)
    assert resp.status_code == 403


def test_update_category(client, seed_users, seed_category):
    headers = {"Authorization": f"Bearer {seed_users['admin_token']}"}
    resp = client.patch(
        f"/api/v1/categories/{seed_category}",
        json={"name": "Information Technology"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Information Technology"
