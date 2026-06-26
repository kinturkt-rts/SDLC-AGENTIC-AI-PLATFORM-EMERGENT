"""Alerts router — offboarding, warranty, license overages."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser, require_roles
from app.models.asset import Asset
from app.models.assignment import Assignment
from app.models.employee import Employee
from schemas.alerts import LicenseOverageAlert, OffboardingAlert
from schemas.asset import AssetOut

router = APIRouter(tags=["alerts"])


# ── GET /alerts/offboarding ──────────────────────────────────────────────────
@router.get("/offboarding", response_model=list[OffboardingAlert])
def offboarding_alerts(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("it_admin", "it_staff")),
) -> list[OffboardingAlert]:
    """Inactive employees with active assignments."""
    # Find inactive employees who have at least one active assignment
    inactive_employees = db.scalars(
        select(Employee).where(Employee.is_active == False)
    ).all()

    results = []
    for emp in inactive_employees:
        active_assignments = db.scalars(
            select(Assignment).where(
                Assignment.employee_id == str(emp.id),
                Assignment.returned_at == None,
            )
        ).all()
        if active_assignments:
            # Get asset info for each active assignment
            assets_info = []
            for a in active_assignments:
                asset = db.query(Asset).filter(Asset.id == a.asset_id).first()
                if asset:
                    assets_info.append({
                        "asset_id": str(asset.id),
                        "asset_type": str(asset.asset_type),
                        "manufacturer": asset.manufacturer,
                        "model": asset.model,
                    })
            results.append(OffboardingAlert(
                employee_id=str(emp.id),
                full_name=emp.full_name,
                email=emp.email,
                department=emp.department,
                deactivated_at=emp.deactivated_at,
                active_assets=assets_info,
            ))
    return results


# ── GET /alerts/warranty ─────────────────────────────────────────────────────
@router.get("/warranty", response_model=list[AssetOut])
def warranty_alerts(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    days: int = Query(default=30),
) -> list[AssetOut]:
    """Assets with warranty expiring within N days, excluding retired."""
    cutoff = date.today() + timedelta(days=days)
    rows = db.scalars(
        select(Asset).where(
            Asset.warranty_end_date <= cutoff,
            Asset.warranty_end_date != None,
            Asset.status != "retired",
        )
    ).all()
    return [AssetOut.model_validate(r) for r in rows]


# ── GET /alerts/license-overages ─────────────────────────────────────────────
@router.get("/license-overages", response_model=list[LicenseOverageAlert])
def license_overage_alerts(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("it_admin", "it_staff")),
) -> list[LicenseOverageAlert]:
    """License assets where seats_in_use > seats_purchased."""
    # Get all license assets
    license_assets = db.scalars(
        select(Asset).where(Asset.asset_type == "license")
    ).all()

    results = []
    for asset in license_assets:
        if asset.seats_purchased is None:
            continue
        seats_in_use = db.scalar(
            select(func.count(Assignment.id)).where(
                Assignment.asset_id == str(asset.id),
                Assignment.returned_at == None,
            )
        ) or 0
        if seats_in_use > asset.seats_purchased:
            results.append(LicenseOverageAlert(
                asset_id=str(asset.id),
                manufacturer=asset.manufacturer,
                model=asset.model,
                seats_purchased=asset.seats_purchased,
                seats_in_use=seats_in_use,
            ))
    return results
