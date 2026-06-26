"""Stats router for review analytics."""

from datetime import datetime, timedelta
from fastapi import APIRouter
from sqlalchemy import func, select

from app.dependencies import DbSession, ApiKeyDep
from app.models.review import Review, RiskBandEnum
from schemas.review import StatsOut


router = APIRouter()


@router.get("", response_model=StatsOut)
def get_stats(
    db: DbSession,
    api_key: ApiKeyDep,
):
    """Get review statistics for last 30 days."""
    # Calculate 30 days ago
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Query for counts by risk band in last 30 days
    risk_band_counts = {}
    for risk_band in RiskBandEnum:
        count = db.scalar(
            select(func.count(Review.id))
            .where(Review.submitted_at >= thirty_days_ago)
            .where(Review.risk_band == risk_band)
        ) or 0
        risk_band_counts[risk_band.value] = count
    
    # Calculate average risk score for last 30 days
    avg_result = db.scalar(
        select(func.avg(Review.risk_score))
        .where(Review.submitted_at >= thirty_days_ago)
    )
    avg_risk_score = float(avg_result) if avg_result is not None else 0.0
    
    return StatsOut(
        last_30_days=risk_band_counts,
        avg_risk_score=round(avg_risk_score, 2)
    )