"""Reviews router for PR diff analysis endpoints."""

import json
import re
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dependencies import DbSession, ApiKeyDep
from app.models.review import Review, RiskBandEnum
from app.services.bedrock_client import get_bedrock_client
from app.services.prompts import DIFF_ANALYSIS_PROMPT
from schemas.review import ReviewCreate, ReviewOut, ReviewListPage, StatsOut
from app.config import get_settings


router = APIRouter()


def calculate_diff_metrics(diff_text: str) -> tuple[int, int, int]:
    """Extract file count, lines added, and lines removed from diff."""
    files = set()
    lines_added = 0
    lines_removed = 0
    
    for line in diff_text.split('\n'):
        # Track files
        if line.startswith('diff --git') or line.startswith('--- ') or line.startswith('+++ '):
            if line.startswith('diff --git'):
                # Extract file path from "diff --git a/path b/path"
                match = re.search(r'diff --git a/(.+?) b/', line)
                if match:
                    files.add(match.group(1))
        # Count line changes
        elif line.startswith('+') and not line.startswith('+++'):
            lines_added += 1
        elif line.startswith('-') and not line.startswith('---'):
            lines_removed += 1
    
    return len(files), lines_added, lines_removed


def apply_risk_heuristics(base_score: int, diff_text: str, file_count: int, lines_added: int, lines_removed: int) -> int:
    """Apply heuristics to adjust base risk score."""
    adjusted_score = base_score
    
    # +15 for migrations/
    if 'migrations/' in diff_text.lower():
        adjusted_score += 15
    
    # +10 for secrets/security files
    if any(term in diff_text.lower() for term in ['secret', 'password', 'key', 'auth', 'security']):
        adjusted_score += 10
    
    # -10 for small changes (<30 lines total)
    total_lines = lines_added + lines_removed
    if total_lines < 30:
        adjusted_score -= 10
    
    # Clamp to 0-100 range
    return max(0, min(100, adjusted_score))


def determine_risk_band(risk_score: int) -> RiskBandEnum:
    """Determine risk band from score: 0-30=low, 31-70=medium, 71-100=high."""
    if risk_score <= 30:
        return RiskBandEnum.LOW
    elif risk_score <= 70:
        return RiskBandEnum.MEDIUM
    else:
        return RiskBandEnum.HIGH


@router.post("/", response_model=ReviewOut, status_code=201)
def create_review(
    body: ReviewCreate,
    db: DbSession,
    api_key: ApiKeyDep,
):
    """Analyze PR diff and create review record."""
    settings = get_settings()
    
    # Validate input limits
    if len(body.diff_text.encode('utf-8')) > settings.max_diff_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Diff text exceeds {settings.max_diff_size_mb}MB limit"
        )
    
    if len(body.title) > settings.max_title_length:
        raise HTTPException(
            status_code=413, 
            detail=f"Title exceeds {settings.max_title_length} characters"
        )
    
    # Calculate diff metrics
    file_count, lines_added, lines_removed = calculate_diff_metrics(body.diff_text)
    
    # Call Bedrock for AI analysis
    bedrock = get_bedrock_client()

    try:
        response_text = bedrock.invoke_text(
            system_message=DIFF_ANALYSIS_PROMPT,
            user_message=f"Diff to analyze:\n{body.diff_text}",
        )
        # Try to parse JSON response
        try:
            ai_result = json.loads(response_text)
            summary = ai_result.get("summary", "Analysis completed")
            base_risk_score = int(ai_result.get("risk_score", 50))
        except (json.JSONDecodeError, ValueError, KeyError):
            # Fallback if AI doesn't return proper JSON
            summary = "AI analysis completed with non-JSON response"
            base_risk_score = 50  # Default moderate risk
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI analysis failed: {str(e)}"
        )
    
    # Apply heuristics
    final_risk_score = apply_risk_heuristics(
        base_risk_score, body.diff_text, file_count, lines_added, lines_removed
    )
    risk_band = determine_risk_band(final_risk_score)
    
    # Create review record
    review = Review(
        title=body.title,
        diff_text=body.diff_text,
        file_count=file_count,
        lines_added=lines_added,
        lines_removed=lines_removed,
        summary=summary,
        risk_score=final_risk_score,
        risk_band=risk_band,
        model_id=settings.bedrock_model_id,
        created_by=api_key  # Use API key as created_by identifier
    )
    
    db.add(review)
    db.commit()
    db.refresh(review)
    
    return review


@router.get("/", response_model=ReviewListPage)
def list_reviews(
    db: DbSession,
    api_key: ApiKeyDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    risk_band: Optional[str] = Query(default=None),
):
    """List reviews with optional filtering by risk band."""
    query = select(Review)
    
    # Apply risk_band filter if provided
    if risk_band:
        try:
            risk_band_enum = RiskBandEnum(risk_band)
            query = query.where(Review.risk_band == risk_band_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid risk_band. Must be one of: {[e.value for e in RiskBandEnum]}"
            )
    
    # Get total count
    count_query = select(func.count(Review.id))
    if risk_band:
        count_query = count_query.where(Review.risk_band == RiskBandEnum(risk_band))
    
    total = db.scalar(count_query) or 0
    
    # Get paginated results
    query = query.order_by(Review.submitted_at.desc()).offset(offset).limit(limit)
    reviews = list(db.scalars(query).all())
    
    return ReviewListPage(
        items=reviews,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/{id}", response_model=ReviewOut)
def get_review(
    id: str,
    db: DbSession,
    api_key: ApiKeyDep,
):
    """Get a specific review by ID."""
    review = db.scalar(select(Review).where(Review.id == id))
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@router.get("/", response_model=StatsOut, include_in_schema=False)  # Hide from OpenAPI
def _stats_endpoint():
    """Placeholder - actual stats endpoint is separate."""
    pass