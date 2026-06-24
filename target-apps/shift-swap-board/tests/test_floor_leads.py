"""Tests for floor-lead management."""
from datetime import date, timedelta


def _next_monday() -> str:
    today = date.today()
    days_ahead = 7 - today.weekday()  # next Monday
    return (today + timedelta(days=days_ahead)).isoformat()


def test_create_floor_lead(client, seeded, auth_headers):
    monday = _next_monday()
    resp = client.post(
        "/floor-leads",
        json={"week_start": monday, "floor_lead_user_id": seeded["lead_id"]},
        headers=auth_headers("admin"),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["week_start"] == monday


def test_create_floor_lead_not_monday(client, seeded, auth_headers):
    # Use a Tuesday
    today = date.today()
    tuesday = today + timedelta(days=(1 - today.weekday()) % 7 + 7)
    if tuesday.weekday() != 1:
        tuesday = today + timedelta(days=1)  # fallback
        while tuesday.weekday() != 1:
            tuesday += timedelta(days=1)
    resp = client.post(
        "/floor-leads",
        json={"week_start": tuesday.isoformat(), "floor_lead_user_id": seeded["lead_id"]},
        headers=auth_headers("admin"),
    )
    assert resp.status_code == 422


def test_create_floor_lead_duplicate_week(client, seeded, auth_headers):
    monday = _next_monday()
    headers = auth_headers("admin")
    client.post("/floor-leads", json={"week_start": monday, "floor_lead_user_id": seeded["lead_id"]}, headers=headers)
    resp = client.post("/floor-leads", json={"week_start": monday, "floor_lead_user_id": seeded["lead_id"]}, headers=headers)
    assert resp.status_code == 409


def test_create_floor_lead_wrong_role(client, seeded, auth_headers):
    monday = _next_monday()
    resp = client.post(
        "/floor-leads",
        json={"week_start": monday, "floor_lead_user_id": seeded["staff1_id"]},
        headers=auth_headers("admin"),
    )
    assert resp.status_code == 422


def test_list_floor_leads(client, seeded, auth_headers):
    resp = client.get("/floor-leads", headers=auth_headers("admin"))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_floor_leads_forbidden_staff(client, seeded, auth_headers):
    resp = client.get("/floor-leads", headers=auth_headers("staff"))
    assert resp.status_code == 403
