"""Technician endpoint tests."""


def test_create_technician(client, dispatcher_headers):
    resp = client.post("/api/v1/technicians", json={
        "name": "New Tech",
        "skills": ["residential"],
        "active": True
    }, headers=dispatcher_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "New Tech"
    assert data["skills"] == ["residential"]


def test_list_technicians(client, dispatcher_headers, seed_data):
    resp = client.get("/api/v1/technicians", headers=dispatcher_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2


def test_update_technician_skills(client, dispatcher_headers, seed_data):
    tech_id = seed_data["tech1_id"]
    resp = client.put(f"/api/v1/technicians/{tech_id}", json={
        "skills": ["residential", "commercial", "install"]
    }, headers=dispatcher_headers)
    assert resp.status_code == 200
    assert "install" in resp.json()["skills"]


def test_technician_user_cannot_create(client, tech_headers):
    resp = client.post("/api/v1/technicians", json={
        "name": "Blocked Tech",
        "skills": [],
        "active": True
    }, headers=tech_headers)
    assert resp.status_code == 403
