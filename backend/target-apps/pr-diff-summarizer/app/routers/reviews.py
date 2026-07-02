"""Reviews endpoints."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.dependencies import require_api_key
from app.config import get_settings
from app.models.review import Review
from app.services.diff_parser import parse_diff
from app.services.risk_scorer import apply_heuristics, derive_risk_band
from app.services.bedrock_client import invoke_summarize
from schemas.review import ReviewCreate, ReviewOut, ReviewListResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=ReviewOut, status_code=201)
def create_review(
    body: ReviewCreate,
    api_key: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    """Submit a diff for review and summarization."""
    settings = get_settings()

    # Diff size guard
    if len(body.diff_text.encode("utf-8")) > settings.max_diff_bytes:
        raise HTTPException(
            status_code=422,
            detail=f"diff_text exceeds maximum size of {settings.max_diff_bytes} bytes",
        )

    # Parse diff statistics
    stats = parse_diff(body.diff_text)
    total_changed = stats["lines_added"] + stats["lines_removed"]

    # Call Bedrock for summary
    try:
        bedrock_result = invoke_summarize(body.diff_text, body.title)
    except ValueError:
        raise HTTPException(status_code=502, detail="bedrock_parse_error")

    # Apply heuristic adjustments
    base_score = bedrock_result["risk_score"]
    final_score = apply_heuristics(base_score, body.diff_text, total_changed)
    risk_band = derive_risk_band(final_score)

    # Persist
    review = Review(
        title=body.title,
        diff_text=body.diff_text,
        file_count=stats["file_count"],
        lines_added=stats["lines_added"],
        lines_removed=stats["lines_removed"],
        summary=bedrock_result["summary"],
        risk_factors=bedrock_result["risk_factors"],
        risk_score=final_score,
        risk_band=risk_band,
        model_id=settings.bedrock_model_id,
        created_by=api_key[:8] if api_key else None,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    logger.info(
        "Review created",
        extra={"risk_band": risk_band, "risk_score": final_score},
    )

    return review


@router.get("", response_model=ReviewListResponse)
def list_reviews(
    api_key: str = Depends(require_api_key),
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    risk_band: Optional[str] = Query(default=None),
):
    """List reviews with optional risk_band filter and pagination."""
    query = select(Review)
    count_query = select(func.count(Review.id))

    if risk_band:
        if risk_band not in ("low", "medium", "high"):
            raise HTTPException(status_code=422, detail="risk_band must be low, medium, or high")
        query = query.where(Review.risk_band == risk_band)
        count_query = count_query.where(Review.risk_band == risk_band)

    total = db.scalar(count_query) or 0

    query = query.order_by(Review.submitted_at.desc()).offset(offset).limit(limit)
    rows = list(db.scalars(query).all())

    return ReviewListResponse(items=rows, total=total)


@router.get("/{review_id}", response_model=ReviewOut)
def get_review(
    review_id: str,
    api_key: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    """Retrieve a single review by ID."""
    review = db.scalar(select(Review).where(Review.id == review_id))
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review
