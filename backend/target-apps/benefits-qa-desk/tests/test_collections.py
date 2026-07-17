"""Collection endpoint tests."""


def test_create_collection_contributor(client, contributor_headers, seed_users):
    resp = client.post(
        "/api/v1/collections",
        json={"name": "Test Collection", "description": "A test"},
        headers=contributor_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Collection"
    assert "id" in data


def test_create_collection_employee_forbidden(client, employee_headers, seed_users):
    resp = client.post(
        "/api/v1/collections",
        json={"name": "Should Fail"},
        headers=employee_headers,
    )
    assert resp.status_code == 403


def test_create_duplicate_collection(client, contributor_headers, seed_users):
    client.post(
        "/api/v1/collections",
        json={"name": "Dup"},
        headers=contributor_headers,
    )
    resp = client.post(
        "/api/v1/collections",
        json={"name": "Dup"},
        headers=contributor_headers,
    )
    assert resp.status_code == 409


def test_list_collections(client, contributor_headers, employee_headers, seed_users):
    client.post(
        "/api/v1/collections",
        json={"name": "Col1"},
        headers=contributor_headers,
    )
    resp = client.get("/api/v1/collections", headers=employee_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


def test_patch_collection(client, contributor_headers, seed_users):
    create_resp = client.post(
        "/api/v1/collections",
        json={"name": "PatchMe"},
        headers=contributor_headers,
    )
    coll_id = create_resp.json()["id"]
    resp = client.patch(
        f"/api/v1/collections/{coll_id}",
        json={"description": "Updated"},
        headers=contributor_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated"
