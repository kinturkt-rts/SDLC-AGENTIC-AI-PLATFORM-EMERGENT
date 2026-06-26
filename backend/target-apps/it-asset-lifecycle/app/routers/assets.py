"""Assets router — CRUD + assign/return/retire."""
from __future__ import annotations

from datetime import date, timedelta, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser, require_roles
from app.models.asset import Asset
from app.models.assignment import Assignment
from app.models.assignment_history import AssignmentHistory
from app.models.employee import Employee
from app.models.pg_types import AssetStatus, AssetType, AssignmentEventType
from app.services.encryption import encrypt_license_key
from schemas.asset import AssetCreate, AssetOut, AssetUpdate
from schemas.assignment import AssignmentOut, AssignRequest, ReturnRequest

router = APIRouter(tags=["assets"])


# ── GET /assets ──────────────────────────────────────────────────────────────
@router.get("", response_model=list[AssetOut])
def list_assets(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    warranty_expiring_within_days: Optional[int] = Query(default=None),
) -> list[AssetOut]:
    """List assets with optional filters."""
    # Validate enum values
    if type is not None:
        valid_types = [e.value for e in AssetType]
        if type not in valid_types:
            raise HTTPException(status_code=422, detail=f"Invalid type. Must be one of: {valid_types}")
    if status is not None:
        valid_statuses = [e.value for e in AssetStatus]
        if status not in valid_statuses:
            raise HTTPException(status_code=422, detail=f"Invalid status. Must be one of: {valid_statuses}")

    query = select(Asset)
    if type:
        query = query.where(Asset.asset_type == type)
    if status:
        query = query.where(Asset.status == status)
    if warranty_expiring_within_days is not None:
        cutoff = date.today() + timedelta(days=warranty_expiring_within_days)
        query = query.where(Asset.warranty_end_date <= cutoff, Asset.warranty_end_date != None)

    rows = db.scalars(query).all()
    return [AssetOut.model_validate(r) for r in rows]


# ── POST /assets ─────────────────────────────────────────────────────────────
@router.post("", response_model=AssetOut, status_code=201)
def create_asset(
    body: AssetCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("it_admin")),
) -> AssetOut:
    """Create a new asset. License type requires seats_purchased > 0."""
    if body.asset_type == "license":
        if not body.seats_purchased or body.seats_purchased <= 0:
            raise HTTPException(status_code=422, detail="seats_purchased must be > 0 for license assets")

    asset = Asset(
        asset_type=body.asset_type,
        manufacturer=body.manufacturer,
        model=body.model,
        serial_number=body.serial_number,
        seats_purchased=body.seats_purchased,
        purchase_date=body.purchase_date,
        purchase_cost=body.purchase_cost,
        warranty_end_date=body.warranty_end_date,
        status="in_stock",
    )

    if body.license_key:
        asset.license_key_encrypted = encrypt_license_key(body.license_key)
        asset.license_key_last4 = body.license_key[-4:]

    db.add(asset)
    db.commit()
    db.refresh(asset)
    return AssetOut.model_validate(asset)


# ── PATCH /assets/{id} ───────────────────────────────────────────────────────
@router.patch("/{asset_id}", response_model=AssetOut)
def update_asset(
    asset_id: str,
    body: AssetUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("it_admin")),
) -> AssetOut:
    """Update asset fields (it_admin only)."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    updates = body.model_dump(exclude_unset=True)
    if "license_key" in updates:
        lk = updates.pop("license_key")
        if lk:
            asset.license_key_encrypted = encrypt_license_key(lk)
            asset.license_key_last4 = lk[-4:]
        else:
            asset.license_key_encrypted = None
            asset.license_key_last4 = None

    for k, v in updates.items():
        setattr(asset, k, v)

    db.commit()
    db.refresh(asset)
    return AssetOut.model_validate(asset)


# ── POST /assets/{id}/assign ─────────────────────────────────────────────────
@router.post("/{asset_id}/assign", response_model=AssignmentOut, status_code=201)
def assign_asset(
    asset_id: str,
    body: AssignRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("it_admin", "it_staff")),
) -> AssignmentOut:
    """Assign asset to an employee. Enforces single-assignment and seat limits."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    if asset.status == "retired":
        raise HTTPException(status_code=422, detail="Cannot assign a retired asset")

    # Check employee exists
    employee = db.query(Employee).filter(Employee.id == body.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Count active assignments for this asset
    active_count = db.scalar(
        select(func.count(Assignment.id)).where(
            Assignment.asset_id == asset_id,
            Assignment.returned_at == None,
        )
    ) or 0

    if asset.asset_type == "license":
        # Seat limit enforcement
        if asset.seats_purchased and active_count >= asset.seats_purchased:
            raise HTTPException(status_code=422, detail="no seats available")
    else:
        # Single active assignment enforcement
        if active_count > 0:
            raise HTTPException(status_code=422, detail="asset already assigned")

    # Create assignment
    assignment = Assignment(
        asset_id=asset_id,
        employee_id=body.employee_id,
        assigned_at=datetime.now(timezone.utc),
        assigned_by=str(current_user.id),
    )
    db.add(assignment)

    # Update asset status
    asset.status = "assigned"

    # Append to assignment history
    history = AssignmentHistory(
        asset_id=asset_id,
        employee_id=body.employee_id,
        event_type="assign",
        event_at=datetime.now(timezone.utc),
        actor_id=str(current_user.id),
    )
    db.add(history)

    db.commit()
    db.refresh(assignment)
    return AssignmentOut.model_validate(assignment)


# ── POST /assets/{id}/return ─────────────────────────────────────────────────
@router.post("/{asset_id}/return", response_model=AssignmentOut)
def return_asset(
    asset_id: str,
    body: ReturnRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("it_admin", "it_staff")),
) -> AssignmentOut:
    """Return an asset — set returned_at and update status."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Validate condition
    if body.condition not in ("in_stock", "repair"):
        raise HTTPException(status_code=422, detail="condition must be 'in_stock' or 'repair'")

    # Find active assignment
    assignment = db.query(Assignment).filter(
        Assignment.asset_id == asset_id,
        Assignment.returned_at == None,
    ).first()
    if not assignment:
        raise HTTPException(status_code=422, detail="No active assignment found for this asset")

    now = datetime.now(timezone.utc)
    assignment.returned_at = now
    assignment.return_condition_note = body.note

    # Update asset status
    asset.status = body.condition

    # Append to assignment history
    history = AssignmentHistory(
        asset_id=asset_id,
        employee_id=str(assignment.employee_id),
        event_type="return",
        event_at=now,
        actor_id=str(current_user.id),
        condition_note=body.note,
    )
    db.add(history)

    db.commit()
    db.refresh(assignment)
    return AssignmentOut.model_validate(assignment)


# ── POST /assets/{id}/retire ─────────────────────────────────────────────────
@router.post("/{asset_id}/retire", response_model=AssetOut)
def retire_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("it_admin")),
) -> AssetOut:
    """Retire an asset — only if no active assignments."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    if asset.status == "assigned":
        raise HTTPException(status_code=422, detail="Cannot retire an assigned asset")

    # Double-check no active assignments
    active_count = db.scalar(
        select(func.count(Assignment.id)).where(
            Assignment.asset_id == asset_id,
            Assignment.returned_at == None,
        )
    ) or 0
    if active_count > 0:
        raise HTTPException(status_code=422, detail="Cannot retire an asset with active assignments")

    asset.status = "retired"
    db.commit()
    db.refresh(asset)
    return AssetOut.model_validate(asset)
