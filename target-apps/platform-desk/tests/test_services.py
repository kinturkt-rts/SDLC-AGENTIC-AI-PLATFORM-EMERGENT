"""Tests for Service catalog CRUD."""
import uuid


def test_create_service(client, api_headers):
    body = {
        "name": "new-service",
        "owning_team": "Team A",
        "criticality_tier": 2,
        "active_support": True,
    }
    resp = client.post("/api/v1/services", json=body, headers=api_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "new-service"
    assert data["owning_team"] == "Team A"
    assert data["criticality_tier"] == 2


def test_create_service_duplicate_name(client, api_headers, sample_service):
    body = {
        "name": sample_service.name,
        "owning_team": "Another Team",
        "criticality_tier": 1,
        "active_support": True,
    }
    resp = client.post("/api/v1/services", json=body, headers=api_headers)
    assert resp.status_code == 409


def test_list_services(client, api_headers, sample_service):
    resp = client.get("/api/v1/services", headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


def test_get_service(client, api_headers, sample_service):
    resp = client.get(f"/api/v1/services/{sample_service.id}", headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(sample_service.id)


def test_update_service(client, api_headers, sample_service):
    resp = client.put(
        f"/api/v1/services/{sample_service.id}",
        json={"owning_team": "Updated Team"},
        headers=api_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["owning_team"] == "Updated Team"


def test_delete_service(client, api_headers, sample_service):
    resp = client.delete(f"/api/v1/services/{sample_service.id}", headers=api_headers)
    assert resp.status_code == 204


def test_unauthorized_without_key(client):
    resp = client.get("/api/v1/services")
    assert resp.status_code == 401
