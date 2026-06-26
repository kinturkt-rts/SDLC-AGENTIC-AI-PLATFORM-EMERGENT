"""Tests for stats endpoint."""

from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.review import Review, RiskBandEnum


def test_get_stats_empty(client: TestClient, api_headers: dict):
    """Test stats with no data."""
    response = client.get("/stats", headers=api_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert data["last_30_days"]["low"] == 0
    assert data["last_30_days"]["medium"] == 0 
    assert data["last_30_days"]["high"] == 0
    assert data["avg_risk_score"] == 0.0


def test_get_stats_with_data(client: TestClient, api_headers: dict, db_session: Session):
    """Test stats with review data."""
    # Create reviews with different risk bands
    reviews = [
        Review(
            title="Low risk PR",
            diff_text="minor change",
            file_count=1,
            lines_added=1,
            lines_removed=0,
            summary="Minor change",
            risk_score=15,
            risk_band=RiskBandEnum.LOW,
            model_id="test-model",
            created_by="test-key"
        ),
        Review(
            title="Medium risk PR",
            diff_text="moderate change",
            file_count=3,
            lines_added=25,
            lines_removed=10,
            summary="Moderate change",
            risk_score=55,
            risk_band=RiskBandEnum.MEDIUM,
            model_id="test-model",
            created_by="test-key"
        ),
        Review(
            title="High risk PR",
            diff_text="major change with migrations",
            file_count=10,
            lines_added=100,
            lines_removed=50,
            summary="Major database migration",
            risk_score=85,
            risk_band=RiskBandEnum.HIGH,
            model_id="test-model",
            created_by="test-key"
        ),
    ]
    
    for review in reviews:
        db_session.add(review)
    db_session.commit()
    
    response = client.get("/stats", headers=api_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert data["last_30_days"]["low"] == 1
    assert data["last_30_days"]["medium"] == 1
    assert data["last_30_days"]["high"] == 1
    # Average of 15, 55, 85 = 51.67
    assert abs(data["avg_risk_score"] - 51.67) < 0.1


def test_get_stats_old_data_excluded(client: TestClient, api_headers: dict, db_session: Session):
    """Test that reviews older than 30 days are excluded from stats."""
    # Create old review (35 days ago)
    old_review = Review(
        title="Old PR",
        diff_text="old change",
        file_count=1,
        lines_added=5,
        lines_removed=0,
        summary="Old change",
        risk_score=75,
        risk_band=RiskBandEnum.HIGH,
        model_id="test-model",
        created_by="test-key",
        submitted_at=datetime.utcnow() - timedelta(days=35)
    )
    
    # Create recent review
    recent_review = Review(
        title="Recent PR", 
        diff_text="recent change",
        file_count=1,
        lines_added=2,
        lines_removed=0,
        summary="Recent change",
        risk_score=25,
        risk_band=RiskBandEnum.LOW,
        model_id="test-model",
        created_by="test-key"
    )
    
    db_session.add(old_review)
    db_session.add(recent_review)
    db_session.commit()
    
    response = client.get("/stats", headers=api_headers)
    assert response.status_code == 200
    
    data = response.json()
    # Only recent review should be counted
    assert data["last_30_days"]["low"] == 1
    assert data["last_30_days"]["medium"] == 0
    assert data["last_30_days"]["high"] == 0
    assert data["avg_risk_score"] == 25.0


def test_get_stats_missing_auth(client: TestClient):
    """Test stats endpoint without API key."""
    response = client.get("/stats")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key"