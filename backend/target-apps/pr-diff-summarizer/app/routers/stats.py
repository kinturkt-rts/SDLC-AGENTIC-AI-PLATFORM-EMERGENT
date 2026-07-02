"""Stats endpoint."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func, case

from app.database import get_db
from app.dependencies import require_api_key
from app.models.review import Review
from schemas.review import StatsResponse, Last30Days

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
def get_stats(
    api_key: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    """Return risk distribution stats for the last 30 days."""
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    query = select(
        func.count(
            case(
                (Review.risk_band == "low", 1),
            )
        ).label("low"),
        func.count(
            case(
                (Review.risk_band == "medium", 1),
            )
        ).label("medium"),
        func.count(
            case(
                (Review.risk_band == "high", 1),
            )
        ).label("high"),
        func.coalesce(func.avg(Review.risk_score), 0).label("avg_score"),
    ).where(Review.submitted_at >= thirty_days_ago)

    result = db.execute(query).one()

    return StatsResponse(
        last_30_days=Last30Days(
            low=result.low,
            medium=result.medium,
            high=result.high,
        ),
        avg_risk_score=round(float(result.avg_score), 1),
    )
