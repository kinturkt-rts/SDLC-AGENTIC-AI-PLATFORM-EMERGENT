"""FX Snapshot management routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.dependencies import AdminUser, AuthUser, DbSession
from app.models.fx_snapshot import FxSnapshot
from app.schemas.fx_snapshot import FxSnapshotCreate, FxSnapshotOut

router = APIRouter(tags=["fx-snapshots"])


@router.post("/api/v1/fx-snapshots", response_model=FxSnapshotOut, status_code=201)
def create_fx_snapshot(
    body: FxSnapshotCreate,
    current_user: AdminUser,
    db: DbSession,
) -> FxSnapshot:
    """Insert or update a daily FX snapshot — admin only."""
    existing = db.scalars(
        select(FxSnapshot).where(
            FxSnapshot.currency == body.currency,
            FxSnapshot.date == body.date,
        )
    ).first()

    if existing:
        existing.rate_to_usd = body.rate_to_usd
        db.commit()
        db.refresh(existing)
        return existing

    snapshot = FxSnapshot(
        currency=body.currency,
        date=body.date,
        rate_to_usd=body.rate_to_usd,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


@router.get("/api/v1/fx-snapshots", response_model=list[FxSnapshotOut])
def list_fx_snapshots(
    current_user: AuthUser,
    db: DbSession,
) -> list[FxSnapshot]:
    """List all FX snapshots — any authenticated user."""
    rows = db.scalars(
        select(FxSnapshot).order_by(FxSnapshot.date.desc(), FxSnapshot.currency)
    ).all()
    return list(rows)
