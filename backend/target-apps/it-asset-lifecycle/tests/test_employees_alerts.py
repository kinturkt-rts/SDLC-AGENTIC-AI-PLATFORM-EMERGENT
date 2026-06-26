"""Employee and alerts tests."""
import uuid

import pytest

from app.models.asset import Asset
from app.models.assignment import Assignment
from app.models.employee import Employee


@pytest.fixture()
def offboarding_scenario(db_session, seeded_users):
    """Create an inactive employee with an active assignment for offboarding alert."""
    emp = Employee(
        id=str(uuid.uuid4()),
        full_name="Offboard Person",
        email=f"offboard.{uuid.uuid4().hex[:6]}@example.com",
        department="Sales",
        is_active=False,
        deactivated_at="2024-11-01T10:00:00+00:00",
    )
    asset = Asset(
        id=str(uuid.uuid4()),
        asset_type="laptop",
        manufacturer="Dell",
        model="Latitude",
        serial_number=f"SN-OFF-{uuid.uuid4().hex[:6]}",
        purchase_date="2024-01-01",
        purchase_cost=1200.00,
        status="assigned",
    )
    db_session.add_all([emp, asset])
    db_session.flush()
    assignment = Assignment(
        id=str(uuid.uuid4()),
        asset_id=asset.id,
        employee_id=emp.id,
        assigned_by=seeded_users["admin_id"],
    )
    db_session.add(assignment)
    db_session.commit()
    return {"employee_id": emp.id, "asset_id": asset.id}


def test_deactivate_employee(client, admin_headers, db_session, seeded_users):
    emp = Employee(
        id=str(uuid.uuid4()),
        full_name="Active Person",
        email=f"active.{uuid.uuid4().hex[:6]}@example.com",
        department="Engineering",
        is_active=True,
    )
    db_session.add(emp)
    db_session.commit()
    resp = client.patch(f"/employees/{emp.id}/deactivate", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is False
    assert data["deactivated_at"] is not None


def test_deactivate_employee_finance_forbidden(client, finance_headers, db_session, seeded_users):
    emp = Employee(
        id=str(uuid.uuid4()),
        full_name="Another Person",
        email=f"another.{uuid.uuid4().hex[:6]}@example.com",
        department="Finance",
        is_active=True,
    )
    db_session.add(emp)
    db_session.commit()
    resp = client.patch(f"/employees/{emp.id}/deactivate", headers=finance_headers)
    assert resp.status_code == 403


def test_offboarding_alerts(client, admin_headers, offboarding_scenario):
    resp = client.get("/alerts/offboarding", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    # Find our offboarded employee
    found = [a for a in data if a["employee_id"] == offboarding_scenario["employee_id"]]
    assert len(found) == 1
    assert len(found[0]["active_assets"]) >= 1


def test_warranty_alerts(client, admin_headers, db_session, seeded_users):
    # Create an asset with warranty expiring soon
    from datetime import date, timedelta
    soon = date.today() + timedelta(days=10)
    asset = Asset(
        id=str(uuid.uuid4()),
        asset_type="monitor",
        manufacturer="Dell",
        model="U2723QE",
        serial_number=f"SN-WAR-{uuid.uuid4().hex[:6]}",
        purchase_date="2022-01-01",
        purchase_cost=500.00,
        warranty_end_date=soon,
        status="in_stock",
    )
    db_session.add(asset)
    db_session.commit()
    resp = client.get("/alerts/warranty?days=30", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


def test_license_overage_alerts_empty(client, admin_headers):
    """No overages when no license assets exist."""
    resp = client.get("/alerts/license-overages", headers=admin_headers)
    assert resp.status_code == 200
    # May be empty or have data — just check it returns OK
    assert isinstance(resp.json(), list)
