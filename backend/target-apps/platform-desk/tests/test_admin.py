"""Tests for Admin analytics endpoints."""
import uuid
from datetime import datetime, timezone


def test_reliance_report(client, api_headers, db_session, active_runbook):
    from app.models.incident_touch import IncidentTouch
    touch = IncidentTouch(
        id=str(uuid.uuid4()),
        runbook_id=active_runbook.id,
        ticket_reference="INC-9999",
        role="viewer",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(touch)
    db_session.commit()

    resp = client.get("/api/v1/admin/report/reliance", headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "service_name" in data[0]
    assert "touch_count" in data[0]


def test_analytics(client, api_headers, db_session):
    from app.models.search_event import SearchEvent
    for i in range(3):
        ev = SearchEvent(
            id=str(uuid.uuid4()),
            query_text=f"test query {i}",
            result_count=2,
            top_score=0.8,
            response_time_ms=200 + i * 10,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(ev)
    db_session.commit()

    resp = client.get("/api/v1/admin/analytics", headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "top_queries" in data
    assert "weak_match_queries" in data
    assert "response_time_stats" in data
    assert data["response_time_stats"]["median_ms"] > 0


def test_index_refresh(client, api_headers):
    resp = client.post("/api/v1/admin/index-refresh", headers=api_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert "steps_indexed" in data
