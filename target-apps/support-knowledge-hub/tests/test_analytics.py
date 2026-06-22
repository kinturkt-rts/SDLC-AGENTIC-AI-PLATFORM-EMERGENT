"""Tests for analytics endpoints."""

from datetime import datetime


def _ts(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def test_analytics_gaps_admin(client, auth_headers, seed_article, db_session):
    """Knowledge admin can access analytics gaps."""
    from app.models.search_event import SearchEvent
    evt = SearchEvent(
        id="e5000000-0000-0000-0000-000000000010",
        query_text="how to order new monitor",
        result_article_ids=[],
        result_count=0,
        role="employee",
        timestamp=_ts("2024-02-21T14:00:00+00:00"),
    )
    db_session.add(evt)
    db_session.commit()

    headers = auth_headers("admin")
    resp = client.get("/admin/analytics/gaps", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "gaps" in data
    assert len(data["gaps"]) >= 1


def test_analytics_gaps_employee_forbidden(client, auth_headers, seed_users):
    """Employee cannot access analytics."""
    headers = auth_headers("employee")
    resp = client.get("/admin/analytics/gaps", headers=headers)
    assert resp.status_code == 403


def test_analytics_gaps_leadership(client, auth_headers, seed_article, db_session):
    """Leadership can access analytics gaps."""
    from app.models.search_event import SearchEvent
    evt = SearchEvent(
        id="e5000000-0000-0000-0000-000000000011",
        query_text="parking pass",
        result_article_ids=[],
        result_count=0,
        role="employee",
        timestamp=_ts("2024-02-22T08:45:00+00:00"),
    )
    db_session.add(evt)
    db_session.commit()

    headers = auth_headers("leadership")
    resp = client.get("/admin/analytics/gaps", headers=headers)
    assert resp.status_code == 200
