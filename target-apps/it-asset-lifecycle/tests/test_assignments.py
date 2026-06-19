"""Assignment workflow tests — assign, return, retire."""
import uuid

import pytest

from app.models.asset import Asset
from app.models.employee import Employee


@pytest.fixture()
def employee_and_asset(db_session, seeded_users):
    """Create an employee and a laptop asset for assignment tests."""
    emp = Employee(
        id=str(uuid.uuid4()),
        full_name="Test Employee",
        email=f"test.emp.{uuid.uuid4().hex[:6]}@example.com",
        department="Engineering",
        is_active=True,
    )
    asset = Asset(
        id=str(uuid.uuid4()),
        asset_type="laptop",
        manufacturer="Dell",
        model="Test Model",
        serial_number=f"SN-{uuid.uuid4().hex[:8]}",
        purchase_date="2024-01-01",
        purchase_cost=1000.00,
        status="in_stock",
    )
    db_session.add_all([emp, asset])
    db_session.commit()
    return {"employee_id": emp.id, "asset_id": asset.id}


@pytest.fixture()
def license_asset(db_session, seeded_users):
    """Create a license asset with 2 seats."""
    emp1 = Employee(id=str(uuid.uuid4()), full_name="Emp A", email=f"a.{uuid.uuid4().hex[:6]}@example.com", department="Engineering", is_active=True)
    emp2 = Employee(id=str(uuid.uuid4()), full_name="Emp B", email=f"b.{uuid.uuid4().hex[:6]}@example.com", department="Engineering", is_active=True)
    emp3 = Employee(id=str(uuid.uuid4()), full_name="Emp C", email=f"c.{uuid.uuid4().hex[:6]}@example.com", department="Engineering", is_active=True)
    asset = Asset(
        id=str(uuid.uuid4()),
        asset_type="license",
        manufacturer="JetBrains",
        model="IntelliJ",
        purchase_date="2024-01-01",
        purchase_cost=500.00,
        seats_purchased=2,
        status="in_stock",
    )
    db_session.add_all([emp1, emp2, emp3, asset])
    db_session.commit()
    return {"asset_id": asset.id, "emp1_id": emp1.id, "emp2_id": emp2.id, "emp3_id": emp3.id}


def test_assign_asset(client, admin_headers, employee_and_asset):
    asset_id = employee_and_asset["asset_id"]
    emp_id = employee_and_asset["employee_id"]
    resp = client.post(f"/assets/{asset_id}/assign", json={"employee_id": emp_id}, headers=admin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["asset_id"] == asset_id
    assert data["employee_id"] == emp_id
    assert data["returned_at"] is None


def test_assign_already_assigned(client, admin_headers, employee_and_asset):
    asset_id = employee_and_asset["asset_id"]
    emp_id = employee_and_asset["employee_id"]
    # First assign
    resp = client.post(f"/assets/{asset_id}/assign", json={"employee_id": emp_id}, headers=admin_headers)
    assert resp.status_code == 201
    # Second assign should fail
    resp2 = client.post(f"/assets/{asset_id}/assign", json={"employee_id": emp_id}, headers=admin_headers)
    assert resp2.status_code == 422
    assert resp2.json()["detail"] == "asset already assigned"


def test_return_asset(client, admin_headers, employee_and_asset):
    asset_id = employee_and_asset["asset_id"]
    emp_id = employee_and_asset["employee_id"]
    # Assign first
    client.post(f"/assets/{asset_id}/assign", json={"employee_id": emp_id}, headers=admin_headers)
    # Return
    resp = client.post(f"/assets/{asset_id}/return", json={"condition": "in_stock"}, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["returned_at"] is not None


def test_retire_asset_in_stock(client, admin_headers, employee_and_asset):
    asset_id = employee_and_asset["asset_id"]
    resp = client.post(f"/assets/{asset_id}/retire", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "retired"


def test_retire_assigned_asset_fails(client, admin_headers, employee_and_asset):
    asset_id = employee_and_asset["asset_id"]
    emp_id = employee_and_asset["employee_id"]
    # Assign first
    client.post(f"/assets/{asset_id}/assign", json={"employee_id": emp_id}, headers=admin_headers)
    # Attempt retire
    resp = client.post(f"/assets/{asset_id}/retire", headers=admin_headers)
    assert resp.status_code == 422


def test_license_seat_limit(client, admin_headers, license_asset):
    asset_id = license_asset["asset_id"]
    # Assign first two (should succeed)
    r1 = client.post(f"/assets/{asset_id}/assign", json={"employee_id": license_asset["emp1_id"]}, headers=admin_headers)
    assert r1.status_code == 201
    r2 = client.post(f"/assets/{asset_id}/assign", json={"employee_id": license_asset["emp2_id"]}, headers=admin_headers)
    assert r2.status_code == 201
    # Third should fail
    r3 = client.post(f"/assets/{asset_id}/assign", json={"employee_id": license_asset["emp3_id"]}, headers=admin_headers)
    assert r3.status_code == 422
    assert r3.json()["detail"] == "no seats available"


def test_finance_cannot_assign(client, finance_headers, employee_and_asset):
    asset_id = employee_and_asset["asset_id"]
    emp_id = employee_and_asset["employee_id"]
    resp = client.post(f"/assets/{asset_id}/assign", json={"employee_id": emp_id}, headers=finance_headers)
    assert resp.status_code == 403
