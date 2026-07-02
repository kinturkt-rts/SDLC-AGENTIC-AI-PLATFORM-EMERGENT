"""Tests for stats endpoint."""
from datetime import datetime, timezone
import uuid


def test_stats_returns_counts(client, api_headers, db_session):
    """GET /stats returns risk band counts and avg score."""
    from app.models.review import Review

    # Seed data for stats
    reviews = [
        Review(id=str(uuid.uuid4()), title="Low 1", diff_text="diff", risk_score=20, risk_band="low", submitted_at=datetime.now(timezone.utc)),
        Review(id=str(uuid.uuid4()), title="Low 2", diff_text="diff", risk_score=30, risk_band="low", submitted_at=datetime.now(timezone.utc)),
        Review(id=str(uuid.uuid4()), title="Med 1", diff_text="diff", risk_score=50, risk_band="medium", submitted_at=datetime.now(timezone.utc)),
        Review(id=str(uuid.uuid4()), title="High 1", diff_text="diff", risk_score=80, risk_band="high", submitted_at=datetime.now(timezone.utc)),
    ]
    for r in reviews:
        db_session.add(r)
    db_session.commit()

    response = client.get("/stats", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert "last_30_days" in data
    assert data["last_30_days"]["low"] >= 2
    assert data["last_30_days"]["medium"] >= 1
    assert data["last_30_days"]["high"] >= 1
    assert "avg_risk_score" in data
    assert isinstance(data["avg_risk_score"], float)


def test_stats_no_auth(client):
    """GET /stats without API key returns 401."""
    response = client.get("/stats")
    assert response.status_code == 401
