"""Test sites endpoints."""


def test_create_site_admin(client, seed_users, auth_headers):
    headers = auth_headers("facilities_admin")
    resp = client.post("/api/v1/sites", json={
        "site_code": "NYC-01",
        "name": "NYC Office",
        "address_line": "100 Park Ave, NY",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["site_code"] == "NYC-01"
    assert data["active"] is True


def test_create_site_forbidden_for_requester(client, seed_users, auth_headers):
    headers = auth_headers("requester")
    resp = client.post("/api/v1/sites", json={
        "site_code": "FAIL-01",
        "name": "Fail",
        "address_line": "x",
    }, headers=headers)
    assert resp.status_code == 403


def test_patch_site(client, seed_users, seed_site, auth_headers):
    headers = auth_headers("facilities_admin")
    resp = client.patch(f"/api/v1/sites/{seed_site['id']}", json={
        "name": "Updated Site",
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Site"


def test_no_auth_returns_401(client):
    resp = client.post("/api/v1/sites", json={"site_code": "X", "name": "X", "address_line": "X"})
    assert resp.status_code == 401
