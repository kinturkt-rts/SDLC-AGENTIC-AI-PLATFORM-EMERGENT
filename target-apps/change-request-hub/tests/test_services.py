"""Service catalog tests."""


def test_create_service_manager(client, manager_headers):
    resp = client.post("/api/v1/services", json={"name": "New Service", "owner_team": "Team1", "tier": "tier2"}, headers=manager_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "New Service"
    assert data["tier"] == "tier2"


def test_create_service_requester_forbidden(client, requester_headers):
    resp = client.post("/api/v1/services", json={"name": "X", "owner_team": "T", "tier": "tier1"}, headers=requester_headers)
    assert resp.status_code == 403


def test_list_services(client, manager_headers):
    client.post("/api/v1/services", json={"name": "Svc1", "owner_team": "T", "tier": "tier1"}, headers=manager_headers)
    resp = client.get("/api/v1/services", headers=manager_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert "items" in data


def test_patch_service(client, manager_headers):
    r = client.post("/api/v1/services", json={"name": "PatchMe", "owner_team": "T", "tier": "tier1"}, headers=manager_headers)
    svc_id = r.json()["id"]
    resp = client.patch(f"/api/v1/services/{svc_id}", json={"tier": "tier3"}, headers=manager_headers)
    assert resp.status_code == 200
    assert resp.json()["tier"] == "tier3"
