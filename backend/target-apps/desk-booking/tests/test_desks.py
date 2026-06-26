"""Desk endpoint tests."""
import os


def test_list_desks_public(client, sample_desk):
    """GET /desks is public, returns desks."""
    response = client.get("/desks/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == sample_desk.id
    assert data[0]["label"] == "N-01"


def test_list_desks_filter_zone(client, sample_desk, sample_zone):
    """GET /desks?zone=north filters by zone name."""
    response = client.get("/desks/", params={"zone": "north"})
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = client.get("/desks/", params={"zone": "south"})
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_list_desks_filter_active(client, sample_desk):
    """GET /desks?active=true filters by active status."""
    response = client.get("/desks/", params={"active": True})
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = client.get("/desks/", params={"active": False})
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_create_desk_admin(client, sample_zone, admin_headers):
    """POST /desks requires admin, creates desk."""
    response = client.post(
        "/desks/",
        json={"zone": "north", "label": "N-99"},
        headers=admin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["label"] == "N-99"
    assert data["zone_id"] == sample_zone.id
    assert data["is_active"] is True


def test_create_desk_unauthorized(client, sample_zone):
    """POST /desks without admin key returns 401."""
    response = client.post("/desks/", json={"zone": "north", "label": "N-99"})
    assert response.status_code == 401


def test_patch_desk(client, sample_desk, admin_headers):
    """PATCH /desks/{id} updates desk partially."""
    response = client.patch(
        f"/desks/{sample_desk.id}",
        json={"label": "N-01-UPDATED"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["label"] == "N-01-UPDATED"


def test_patch_desk_deactivate(client, sample_desk, admin_headers):
    """PATCH /desks/{id} can deactivate a desk."""
    response = client.patch(
        f"/desks/{sample_desk.id}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_patch_desk_not_found(client, admin_headers):
    """PATCH /desks/{id} with invalid ID returns 404."""
    response = client.patch(
        "/desks/99999999-9999-9999-9999-999999999999",
        json={"label": "X"},
        headers=admin_headers,
    )
    assert response.status_code == 404
