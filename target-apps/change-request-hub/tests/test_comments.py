"""Comment tests."""
from datetime import datetime, timedelta, timezone


def _future(days=5):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def test_add_comment_requester_own(client, requester_headers, sample_service, sample_environment):
    body = {
        "title": "Comment Test",
        "description": "X",
        "service_id": sample_service,
        "target_environment_id": sample_environment,
        "change_type": "standard",
        "risk": "low",
        "planned_start": _future(5),
        "planned_end": _future(6),
        "rollback_plan": "Plan",
    }
    r = client.post("/api/v1/change-requests", json=body, headers=requester_headers)
    cr_id = r.json()["id"]
    resp = client.post(f"/api/v1/change-requests/{cr_id}/comments", json={"body": "Hello"}, headers=requester_headers)
    assert resp.status_code == 201
    assert resp.json()["body"] == "Hello"


def test_list_comments(client, requester_headers, sample_service, sample_environment):
    body = {
        "title": "List Comments",
        "description": "X",
        "service_id": sample_service,
        "target_environment_id": sample_environment,
        "change_type": "standard",
        "risk": "low",
        "planned_start": _future(5),
        "planned_end": _future(6),
        "rollback_plan": "Plan",
    }
    r = client.post("/api/v1/change-requests", json=body, headers=requester_headers)
    cr_id = r.json()["id"]
    client.post(f"/api/v1/change-requests/{cr_id}/comments", json={"body": "C1"}, headers=requester_headers)
    resp = client.get(f"/api/v1/change-requests/{cr_id}/comments", headers=requester_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
