"""Team endpoint tests."""
from __future__ import annotations

import uuid
from decimal import Decimal
from datetime import date

import pytest


class TestCreateTeam:
    def test_create_success(self, client, auth_as_admin):
        resp = client.post("/api/v1/teams", json={
            "name": "Marketing",
            "description": "Marketing team",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Marketing"

    def test_create_duplicate_409(self, client, auth_as_admin, seed_team):
        resp = client.post("/api/v1/teams", json={"name": "Engineering"})
        assert resp.status_code == 409

    def test_create_forbidden_employee(self, client, auth_as_employee):
        resp = client.post("/api/v1/teams", json={"name": "Test"})
        assert resp.status_code == 403


class TestListTeams:
    def test_list_admin(self, client, auth_as_admin, seed_team):
        resp = client.get("/api/v1/teams")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_list_forbidden_employee(self, client, auth_as_employee):
        resp = client.get("/api/v1/teams")
        assert resp.status_code == 403


class TestManageMembers:
    def test_assign_user(self, client, auth_as_admin, seed_team, seed_user, db_session):
        # Create second team
        from app.models.team import Team
        t2_id = str(uuid.uuid4())
        db_session.add(Team(id=t2_id, name="Sales"))
        db_session.commit()

        resp = client.patch(f"/api/v1/teams/{t2_id}/members", json={
            "user_id": seed_user,
            "action": "assign",
        })
        assert resp.status_code == 200
        assert resp.json()["team_id"] == t2_id

    def test_remove_user(self, client, auth_as_admin, seed_team, seed_user):
        resp = client.patch(f"/api/v1/teams/{seed_team}/members", json={
            "user_id": seed_user,
            "action": "remove",
        })
        assert resp.status_code == 200
        assert resp.json()["team_id"] is None


class TestTeamSummary:
    def test_summary_success(self, client, auth_as_manager, db_session, seed_user, seed_fx):
        # Insert an approved expense for user in the team
        from app.models.expense import Expense
        from tests.conftest import TEAM_ID, EMPLOYEE_ID
        exp = Expense(
            id=str(uuid.uuid4()),
            user_id=EMPLOYEE_ID,
            team_id=TEAM_ID,
            amount=Decimal("100.0000"),
            currency="USD",
            amount_usd=Decimal("100.0000"),
            category="travel",
            expense_date=date(2024, 6, 15),
            status="approved",
        )
        db_session.add(exp)
        db_session.commit()

        resp = client.get(f"/api/v1/teams/{TEAM_ID}/expenses/summary?year=2024&month=6")
        assert resp.status_code == 200
        data = resp.json()
        assert data["team_id"] == TEAM_ID
        assert data["year"] == 2024
        assert data["month"] == 6
        assert Decimal(str(data["grand_total_usd"])) == Decimal("100.0000")

    def test_summary_forbidden_employee(self, client, auth_as_employee, seed_team):
        resp = client.get(f"/api/v1/teams/{seed_team}/expenses/summary?year=2024&month=6")
        assert resp.status_code == 403
