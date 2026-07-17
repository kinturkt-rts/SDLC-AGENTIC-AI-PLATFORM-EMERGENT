"""Expense endpoint integration tests."""
from decimal import Decimal


def test_create_expense(client, emp_headers):
    resp = client.post(
        "/api/v1/expenses",
        json={
            "amount": "100.00",
            "currency": "EUR",
            "category": "travel",
            "description": "Test expense",
            "expense_date": "2024-06-15",
        },
        headers=emp_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "submitted"
    assert data["currency"] == "EUR"
    assert Decimal(data["usd_amount"]) == Decimal("108.0000")
    assert data["employee_id"] == 1


def test_create_expense_invalid_currency(client, emp_headers):
    resp = client.post(
        "/api/v1/expenses",
        json={
            "amount": "100.00",
            "currency": "XYZ",
            "category": "travel",
            "expense_date": "2024-06-15",
        },
        headers=emp_headers,
    )
    assert resp.status_code == 422


def test_create_expense_no_auth(client):
    resp = client.post(
        "/api/v1/expenses",
        json={
            "amount": "100.00",
            "currency": "EUR",
            "category": "travel",
            "expense_date": "2024-06-15",
        },
    )
    assert resp.status_code == 401


def test_patch_expense(client, emp_headers):
    resp = client.post(
        "/api/v1/expenses",
        json={
            "amount": "50.00",
            "currency": "EUR",
            "category": "meals",
            "expense_date": "2024-06-15",
        },
        headers=emp_headers,
    )
    assert resp.status_code == 201
    expense_id = resp.json()["id"]

    resp2 = client.patch(
        f"/api/v1/expenses/{expense_id}",
        json={"amount": "75.00"},
        headers=emp_headers,
    )
    assert resp2.status_code == 200
    assert Decimal(resp2.json()["original_amount"]) == Decimal("75.0000")
    assert Decimal(resp2.json()["usd_amount"]) == Decimal("81.0000")


def test_patch_approved_expense_fails(client, emp_headers, admin_headers):
    resp = client.post(
        "/api/v1/expenses",
        json={
            "amount": "50.00",
            "currency": "EUR",
            "category": "meals",
            "expense_date": "2024-06-15",
        },
        headers=emp_headers,
    )
    expense_id = resp.json()["id"]
    client.post(f"/api/v1/expenses/{expense_id}/approve", headers=admin_headers)
    resp2 = client.patch(
        f"/api/v1/expenses/{expense_id}",
        json={"amount": "100.00"},
        headers=emp_headers,
    )
    assert resp2.status_code == 409


def test_delete_expense(client, emp_headers):
    resp = client.post(
        "/api/v1/expenses",
        json={
            "amount": "50.00",
            "currency": "EUR",
            "category": "other",
            "expense_date": "2024-06-15",
        },
        headers=emp_headers,
    )
    expense_id = resp.json()["id"]
    resp2 = client.delete(f"/api/v1/expenses/{expense_id}", headers=emp_headers)
    assert resp2.status_code == 204
    resp3 = client.get("/api/v1/expenses", headers=emp_headers)
    assert resp3.status_code == 200
    assert all(e["id"] != expense_id for e in resp3.json()["items"])


def test_list_expenses(client, emp_headers):
    for cat in ["travel", "meals"]:
        client.post(
            "/api/v1/expenses",
            json={
                "amount": "100.00",
                "currency": "EUR",
                "category": cat,
                "expense_date": "2024-06-15",
            },
            headers=emp_headers,
        )
    resp = client.get("/api/v1/expenses", headers=emp_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_expenses_filter_category(client, emp_headers):
    client.post(
        "/api/v1/expenses",
        json={"amount": "100.00", "currency": "EUR", "category": "travel", "expense_date": "2024-06-15"},
        headers=emp_headers,
    )
    client.post(
        "/api/v1/expenses",
        json={"amount": "50.00", "currency": "EUR", "category": "meals", "expense_date": "2024-06-15"},
        headers=emp_headers,
    )
    resp = client.get("/api/v1/expenses?category=travel", headers=emp_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_get_expense(client, emp_headers):
    resp = client.post(
        "/api/v1/expenses",
        json={"amount": "100.00", "currency": "EUR", "category": "travel", "expense_date": "2024-06-15"},
        headers=emp_headers,
    )
    expense_id = resp.json()["id"]
    resp2 = client.get(f"/api/v1/expenses/{expense_id}", headers=emp_headers)
    assert resp2.status_code == 200
    assert resp2.json()["id"] == expense_id


def test_approve_expense(client, emp_headers, admin_headers):
    resp = client.post(
        "/api/v1/expenses",
        json={"amount": "100.00", "currency": "EUR", "category": "travel", "expense_date": "2024-06-15"},
        headers=emp_headers,
    )
    expense_id = resp.json()["id"]
    resp2 = client.post(f"/api/v1/expenses/{expense_id}/approve", headers=admin_headers)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "approved"


def test_reject_expense(client, emp_headers, admin_headers):
    resp = client.post(
        "/api/v1/expenses",
        json={"amount": "100.00", "currency": "EUR", "category": "travel", "expense_date": "2024-06-15"},
        headers=emp_headers,
    )
    expense_id = resp.json()["id"]
    resp2 = client.post(f"/api/v1/expenses/{expense_id}/reject", headers=admin_headers)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "rejected"


def test_approve_already_approved_fails(client, emp_headers, admin_headers):
    resp = client.post(
        "/api/v1/expenses",
        json={"amount": "100.00", "currency": "EUR", "category": "travel", "expense_date": "2024-06-15"},
        headers=emp_headers,
    )
    expense_id = resp.json()["id"]
    client.post(f"/api/v1/expenses/{expense_id}/approve", headers=admin_headers)
    resp2 = client.post(f"/api/v1/expenses/{expense_id}/approve", headers=admin_headers)
    assert resp2.status_code == 409


def test_audit_log(client, emp_headers, admin_headers):
    resp = client.post(
        "/api/v1/expenses",
        json={"amount": "100.00", "currency": "EUR", "category": "travel", "expense_date": "2024-06-15"},
        headers=emp_headers,
    )
    expense_id = resp.json()["id"]
    client.post(f"/api/v1/expenses/{expense_id}/approve", headers=admin_headers)
    resp2 = client.get(f"/api/v1/expenses/{expense_id}/audit-log", headers=emp_headers)
    assert resp2.status_code == 200
    entries = resp2.json()
    assert len(entries) == 2
    assert entries[0]["to_status"] == "submitted"
    assert entries[1]["to_status"] == "approved"


def test_non_employee_cannot_create(client, admin_headers):
    resp = client.post(
        "/api/v1/expenses",
        json={"amount": "100.00", "currency": "EUR", "category": "travel", "expense_date": "2024-06-15"},
        headers=admin_headers,
    )
    assert resp.status_code == 403


def test_employee_cannot_approve(client, emp_headers):
    resp = client.post(
        "/api/v1/expenses",
        json={"amount": "100.00", "currency": "EUR", "category": "travel", "expense_date": "2024-06-15"},
        headers=emp_headers,
    )
    expense_id = resp.json()["id"]
    resp2 = client.post(f"/api/v1/expenses/{expense_id}/approve", headers=emp_headers)
    assert resp2.status_code == 403
