"""Expense endpoint tests."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest


class TestCreateExpense:
    def test_create_success(self, client, auth_as_employee, seed_user, seed_fx):
        resp = client.post("/api/v1/expenses", json={
            "amount": "50.00",
            "currency": "GBP",
            "category": "meals",
            "description": "Team lunch",
            "expense_date": "2024-06-01",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "submitted"
        assert data["currency"] == "GBP"
        assert data["category"] == "meals"
        # amount_usd = 50 * 1.27 = 63.5
        assert Decimal(str(data["amount_usd"])) == Decimal("63.5000")

    def test_create_missing_fx_rate(self, client, auth_as_employee, seed_user):
        resp = client.post("/api/v1/expenses", json={
            "amount": "100.00",
            "currency": "JPY",
            "category": "travel",
            "description": "Taxi",
            "expense_date": "2024-06-01",
        })
        assert resp.status_code == 422
        assert "No FX rate available for JPY on 2024-06-01" in resp.json()["detail"]

    def test_create_forbidden_admin(self, client, auth_as_admin, seed_team, seed_fx):
        resp = client.post("/api/v1/expenses", json={
            "amount": "50.00",
            "currency": "USD",
            "category": "other",
            "expense_date": "2024-06-01",
        })
        assert resp.status_code == 403

    def test_create_unauthenticated(self, client):
        resp = client.post("/api/v1/expenses", json={
            "amount": "10.00",
            "currency": "USD",
            "category": "other",
            "expense_date": "2024-06-01",
        })
        assert resp.status_code == 401


class TestListExpenses:
    def test_list_employee_own(self, client, auth_as_employee, seed_expense):
        resp = client.get("/api/v1/expenses")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] >= 1

    def test_list_admin_sees_all(self, client, auth_as_admin, seed_expense):
        resp = client.get("/api/v1/expenses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1


class TestGetExpense:
    def test_get_by_owner(self, client, auth_as_employee, seed_expense):
        resp = client.get(f"/api/v1/expenses/{seed_expense}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == seed_expense

    def test_get_not_found(self, client, auth_as_admin):
        resp = client.get("/api/v1/expenses/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


class TestUpdateExpense:
    def test_update_success(self, client, auth_as_employee, seed_expense, seed_fx):
        resp = client.patch(f"/api/v1/expenses/{seed_expense}", json={
            "description": "Updated description",
        })
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated description"

    def test_update_finalized_409(self, client, auth_as_employee, db_session, seed_expense, seed_fx):
        from app.models.expense import Expense
        exp = db_session.get(Expense, seed_expense)
        exp.status = "approved"
        db_session.commit()

        resp = client.patch(f"/api/v1/expenses/{seed_expense}", json={
            "description": "Try update",
        })
        assert resp.status_code == 409


class TestDeleteExpense:
    def test_delete_success(self, client, auth_as_employee, seed_expense):
        resp = client.delete(f"/api/v1/expenses/{seed_expense}")
        assert resp.status_code == 204

    def test_delete_finalized_409(self, client, auth_as_employee, db_session, seed_expense):
        from app.models.expense import Expense
        exp = db_session.get(Expense, seed_expense)
        exp.status = "approved"
        db_session.commit()

        resp = client.delete(f"/api/v1/expenses/{seed_expense}")
        assert resp.status_code == 409


class TestApproveReject:
    def test_approve_success(self, client, auth_as_admin, seed_expense):
        resp = client.post(f"/api/v1/expenses/{seed_expense}/approve", json={
            "reason": "Valid trip",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["reason"] == "Valid trip"

    def test_reject_success(self, client, auth_as_admin, seed_expense):
        resp = client.post(f"/api/v1/expenses/{seed_expense}/reject", json={
            "reason": "Not valid",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert data["reason"] == "Not valid"

    def test_approve_already_approved_409(self, client, auth_as_admin, db_session, seed_expense):
        from app.models.expense import Expense
        exp = db_session.get(Expense, seed_expense)
        exp.status = "approved"
        db_session.commit()

        resp = client.post(f"/api/v1/expenses/{seed_expense}/approve", json={})
        assert resp.status_code == 409

    def test_approve_forbidden_employee(self, client, auth_as_employee, seed_expense):
        resp = client.post(f"/api/v1/expenses/{seed_expense}/approve", json={})
        assert resp.status_code == 403


class TestAuditLog:
    def test_audit_trail(self, client, auth_as_admin, seed_expense):
        resp = client.get(f"/api/v1/expenses/{seed_expense}/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["action"] == "created"

    def test_audit_forbidden_employee(self, client, auth_as_employee, seed_expense):
        resp = client.get(f"/api/v1/expenses/{seed_expense}/audit")
        assert resp.status_code == 403
