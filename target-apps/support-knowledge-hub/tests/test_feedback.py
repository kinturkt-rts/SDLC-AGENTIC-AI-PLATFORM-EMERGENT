"""Tests for feedback endpoints."""

from datetime import datetime


def _ts(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def test_create_feedback(client, auth_headers, seed_article, db_session):
    """Employee can submit feedback for a search result."""
    # First create a search event
    from app.models.search_event import SearchEvent
    evt = SearchEvent(
        id="e5000000-0000-0000-0000-000000000001",
        query_text="vpn",
        result_article_ids=["c3000000-0000-0000-0000-000000000001"],
        result_count=1,
        role="employee",
        timestamp=_ts("2024-02-20T10:15:00+00:00"),
    )
    db_session.add(evt)
    db_session.commit()

    headers = auth_headers("employee")
    resp = client.post("/feedback", json={
        "search_event_id": "e5000000-0000-0000-0000-000000000001",
        "article_id": "c3000000-0000-0000-0000-000000000001",
        "rating": "helpful",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["rating"] == "helpful"


def test_duplicate_feedback_409(client, auth_headers, seed_article, db_session):
    """Duplicate feedback returns 409."""
    from app.models.search_event import SearchEvent
    from app.models.feedback import Feedback
    evt = SearchEvent(
        id="e5000000-0000-0000-0000-000000000002",
        query_text="test",
        result_article_ids=["c3000000-0000-0000-0000-000000000001"],
        result_count=1,
        role="employee",
        timestamp=_ts("2024-02-20T11:00:00+00:00"),
    )
    db_session.add(evt)
    db_session.commit()

    fb = Feedback(
        id="f6000000-0000-0000-0000-000000000001",
        search_event_id="e5000000-0000-0000-0000-000000000002",
        article_id="c3000000-0000-0000-0000-000000000001",
        rating="helpful",
        timestamp=_ts("2024-02-20T11:05:00+00:00"),
    )
    db_session.add(fb)
    db_session.commit()

    headers = auth_headers("employee")
    resp = client.post("/feedback", json={
        "search_event_id": "e5000000-0000-0000-0000-000000000002",
        "article_id": "c3000000-0000-0000-0000-000000000001",
        "rating": "not_helpful",
    }, headers=headers)
    assert resp.status_code == 409
