"""Reports tests."""
import uuid

import pytest

from app.models.asset import Asset
from app.models.assignment import Assignment
from app.models.employee import Employee


@pytest.fixture()
def valuation_scenario(db_session, seeded_users):
    """Create employees + assets + active assignments for valuation report."""
    emp_eng = Employee(
        id=str(uuid.uuid4()),
        full_name="Engineer",
        email=f"eng.{uuid.uuid4().hex[:6]}@example.com",
        department="Engineering",
        is_active=True,
    )
    emp_sales = Employee(
        id=str(uuid.uuid4()),
        full_name="Salesperson",
        email=f"sales.{uuid.uuid4().hex[:6]}@example.com",
        department="Sales",
        is_active=True,
    )
    asset1 = Asset(
        id=str(uuid.uuid4()),
        asset_type="laptop",
        manufacturer="Dell",
        model="Lat",
        serial_number=f"SN-VAL-{uuid.uuid4().hex[:6]}",
        purchase_date="2024-01-01",
        purchase_cost=1500.00,
        status="assigned",
    )
    asset2 = Asset(
        id=str(uuid.uuid4()),
        asset_type="monitor",
        manufacturer="LG",
        model="27UK",
        serial_number=f"SN-VAL2-{uuid.uuid4().hex[:6]}",
        purchase_date="2024-01-01",
        purchase_cost=500.00,
        status="assigned",
    )
    db_session.add_all([emp_eng, emp_sales, asset1, asset2])
    db_session.flush()

    a1 = Assignment(
        id=str(uuid.uuid4()),
        asset_id=asset1.id,
        employee_id=emp_eng.id,
        assigned_by=seeded_users["admin_id"],
    )
    a2 = Assignment(
        id=str(uuid.uuid4()),
        asset_id=asset2.id,
        employee_id=emp_sales.id,
        assigned_by=seeded_users["admin_id"],
    )
    db_session.add_all([a1, a2])
    db_session.commit()
    return {"eng_dept": "Engineering", "sales_dept": "Sales"}


def test_valuation_report_admin(client, admin_headers, valuation_scenario):
    resp = client.get("/reports/valuation-by-department", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    depts = {d["department"] for d in data}
    assert "Engineering" in depts
    assert "Sales" in depts


def test_valuation_report_finance(client, finance_headers, valuation_scenario):
    resp = client.get("/reports/valuation-by-department", headers=finance_headers)
    assert resp.status_code == 200


def test_valuation_report_staff_forbidden(client, staff_headers, valuation_scenario):
    resp = client.get("/reports/valuation-by-department", headers=staff_headers)
    assert resp.status_code == 403
