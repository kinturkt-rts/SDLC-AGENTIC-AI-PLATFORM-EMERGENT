"""Test comments endpoints."""
import uuid
from datetime import datetime, timezone

from app.models.work_order import WorkOrder


def test_create_comment(client, seed_users, seed_site, auth_headers, db_session):
    # Create a WO as requester
    req_headers = auth_headers("requester")
    resp = client.post("/api/v1/work-orders", json={
        "title": "Comment test",
        "description": "d",
        "category": "general",
        "priority": "low",
        "site_id": seed_site["id"],
    }, headers=req_headers)
    wo_id = resp.json()["id"]

    # Comment as requester (own order)
    resp = client.post(f"/api/v1/work-orders/{wo_id}/comments", json={"body": "My comment"}, headers=req_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["body"] == "My comment"
    assert data["author_id"] is not None


def test_leadership_comment_strips_pii(client, seed_users, seed_site, auth_headers, db_session):
    # Create WO as requester
    req_headers = auth_headers("requester")
    resp = client.post("/api/v1/work-orders", json={
        "title": "PII test",
        "description": "d",
        "category": "access",
        "priority": "normal",
        "site_id": seed_site["id"],
    }, headers=req_headers)
    wo_id = resp.json()["id"]

    # Add comment
    client.post(f"/api/v1/work-orders/{wo_id}/comments", json={"body": "Hello"}, headers=req_headers)

    # Leadership reads comments
    leader_headers = auth_headers("leadership")
    resp = client.get(f"/api/v1/work-orders/{wo_id}/comments", headers=leader_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    # PII stripped for leadership
    assert data[0]["author_id"] is None
    assert data[0]["author_display_name"] is not None


def test_comment_access_denied(client, seed_users, seed_site, auth_headers, db_session):
    # Create WO as requester
    req_headers = auth_headers("requester")
    resp = client.post("/api/v1/work-orders", json={
        "title": "Denied test",
        "description": "d",
        "category": "general",
        "priority": "low",
        "site_id": seed_site["id"],
    }, headers=req_headers)
    wo_id = resp.json()["id"]

    # Technician (not assigned) tries to comment
    tech_headers = auth_headers("technician")
    resp = client.post(f"/api/v1/work-orders/{wo_id}/comments", json={"body": "x"}, headers=tech_headers)
    assert resp.status_code == 403
