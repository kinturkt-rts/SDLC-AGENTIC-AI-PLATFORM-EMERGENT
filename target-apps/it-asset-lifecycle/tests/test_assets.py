"""Asset CRUD tests."""
import uuid
from datetime import date

import pytest


@pytest.fixture()
def sample_asset(client, admin_headers, db_session):
    """Create a sample laptop asset and return its data."""
    from app.models.employee import Employee

    resp = client.post("/assets", json={
        "asset_type": "laptop",
        "manufacturer": "Dell",
        "model": "Latitude 5540",
        "serial_number": f"SN-TEST-{uuid.uuid4().hex[:6]}",
        "purchase_date": "2024-01-15",
        "purchase_cost": "1299.99",
        "warranty_end_date": "2027-01-15",
    }, headers=admin_headers)
    assert resp.status_code == 201
    return resp.json()


def test_create_asset_admin(client, admin_headers):
    resp = client.post("/assets", json={
        "asset_type": "laptop",
        "manufacturer": "Dell",
        "model": "Latitude 5540",
        "serial_number": "SN-UNIQUE-001",
        "purchase_date": "2024-01-15",
        "purchase_cost": "1299.99",
        "warranty_end_date": "2027-01-15",
    }, headers=admin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["asset_type"] == "laptop"
    assert data["status"] == "in_stock"
    assert "license_key_encrypted" not in data


def test_create_asset_finance_forbidden(client, finance_headers):
    resp = client.post("/assets", json={
        "asset_type": "laptop",
        "manufacturer": "HP",
        "model": "EliteBook",
        "purchase_date": "2024-01-15",
        "purchase_cost": "999.00",
    }, headers=finance_headers)
    assert resp.status_code == 403


def test_create_license_without_seats_422(client, admin_headers):
    resp = client.post("/assets", json={
        "asset_type": "license",
        "manufacturer": "Microsoft",
        "model": "Office 365",
        "purchase_date": "2024-01-01",
        "purchase_cost": "5000.00",
    }, headers=admin_headers)
    assert resp.status_code == 422


def test_list_assets_requires_auth(client):
    resp = client.get("/assets")
    assert resp.status_code == 401


def test_list_assets_success(client, admin_headers, sample_asset):
    resp = client.get("/assets", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


def test_list_assets_filter_type(client, admin_headers, sample_asset):
    resp = client.get("/assets?type=laptop", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    for a in data:
        assert a["asset_type"] == "laptop"


def test_patch_asset_admin(client, admin_headers, sample_asset):
    asset_id = sample_asset["id"]
    resp = client.patch(f"/assets/{asset_id}", json={"manufacturer": "Lenovo"}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["manufacturer"] == "Lenovo"


def test_patch_asset_staff_forbidden(client, staff_headers, sample_asset):
    asset_id = sample_asset["id"]
    resp = client.patch(f"/assets/{asset_id}", json={"manufacturer": "HP"}, headers=staff_headers)
    assert resp.status_code == 403


def test_license_key_masking(client, admin_headers):
    """License key encrypted field never exposed; only last4 shown."""
    resp = client.post("/assets", json={
        "asset_type": "license",
        "manufacturer": "Adobe",
        "model": "CC",
        "purchase_date": "2024-01-01",
        "purchase_cost": "2000.00",
        "seats_purchased": 5,
        "license_key": "ABCD-EFGH-IJKL-MNOP",
    }, headers=admin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert "license_key_encrypted" not in data
    assert data["license_key_last4"] == "MNOP"
