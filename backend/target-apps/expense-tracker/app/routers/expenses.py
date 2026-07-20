"""Expense CRUD and status-transition routes."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.dependencies import AdminUser, AuthUser, DbSession
from app.models.audit_log import AuditLog
from app.models.expense import Expense
from app.services.audit import write_audit
from app.services.fx import FXRateNotFound, compute_amount_usd, get_fx_rate
from app.schemas.audit import AuditEntry
from app.schemas.expense import (
    ExpenseCreate,
    ExpenseListResponse,
    ExpenseOut,
    ExpenseUpdate,
    StatusChangeRequest,
)

router = APIRouter(tags=["expenses"])


@router.post("/api/v1/expenses", response_model=ExpenseOut, status_code=201)
def create_expense(
    body: ExpenseCreate,
    current_user: AuthUser,
    db: DbSession,
) -> Expense:
    """Submit a new expense (employee only)."""
    if current_user.role != "employee":
        raise HTTPException(status_code=403, detail="Only employees can submit expenses")

    try:
        rate = get_fx_rate(db, body.currency, body.expense_date)
    except FXRateNotFound as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    amount_usd = compute_amount_usd(body.amount, rate)

    expense = Expense(
        user_id=current_user.user_id,
        team_id=current_user.team_id,
        amount=body.amount,
        currency=body.currency,
        amount_usd=amount_usd,
        category=body.category,
        description=body.description,
        expense_date=body.expense_date,
        status="submitted",
    )
    db.add(expense)
    db.flush()

    write_audit(
        db,
        expense_id=expense.id,
        actor_id=current_user.user_id,
        actor_role=current_user.role,
        action="created",
        from_status=None,
        to_status="submitted",
        metadata={"amount": str(body.amount), "currency": body.currency},
    )
    db.commit()
    db.refresh(expense)
    return expense


@router.get("/api/v1/expenses", response_model=ExpenseListResponse)
def list_expenses(
    current_user: AuthUser,
    db: DbSession,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> dict:
    """List expenses - employee sees own; admin sees all."""
    base = select(Expense).where(Expense.deleted_at.is_(None))

    if current_user.role == "employee":
        base = base.where(Expense.user_id == current_user.user_id)
    elif current_user.role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Forbidden")

    if status_filter:
        base = base.where(Expense.status == status_filter)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    offset = (page - 1) * size
    rows = db.scalars(base.order_by(Expense.created_at.desc()).offset(offset).limit(size)).all()
    return {"items": rows, "total": total, "page": page, "size": size}


@router.get("/api/v1/expenses/{id}", response_model=ExpenseOut)
def get_expense(
    id: str,
    current_user: AuthUser,
    db: DbSession,
) -> Expense:
    """Get single expense - owner or admin."""
    expense = db.scalars(
        select(Expense).where(Expense.id == id, Expense.deleted_at.is_(None))
    ).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    if current_user.role == "employee" and expense.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return expense


@router.patch("/api/v1/expenses/{id}", response_model=ExpenseOut)
def update_expense(
    id: str,
    body: ExpenseUpdate,
    current_user: AuthUser,
    db: DbSession,
) -> Expense:
    """Edit expense - owner only, status must be submitted."""
    if current_user.role != "employee":
        raise HTTPException(status_code=403, detail="Only employees can edit expenses")

    expense = db.scalars(
        select(Expense).where(Expense.id == id, Expense.deleted_at.is_(None))
    ).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    if expense.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if expense.status != "submitted":
        raise HTTPException(status_code=409, detail="Cannot edit a finalized expense")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return expense

    for k, v in updates.items():
        setattr(expense, k, v)

    # Recompute amount_usd when amount or currency or expense_date changed
    try:
        rate = get_fx_rate(db, expense.currency, expense.expense_date)
    except FXRateNotFound as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    expense.amount_usd = compute_amount_usd(expense.amount, rate)
    expense.updated_at = datetime.now(timezone.utc)

    write_audit(
        db,
        expense_id=expense.id,
        actor_id=current_user.user_id,
        actor_role=current_user.role,
        action="updated",
        from_status="submitted",
        to_status="submitted",
        metadata={"updated_fields": list(updates.keys())},
    )
    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/api/v1/expenses/{id}", status_code=204, response_model=None)
def delete_expense(
    id: str,
    current_user: AuthUser,
    db: DbSession,
) -> None:
    """Soft-delete expense - owner only, status must be submitted."""
    if current_user.role != "employee":
        raise HTTPException(status_code=403, detail="Only employees can delete expenses")

    expense = db.scalars(
        select(Expense).where(Expense.id == id, Expense.deleted_at.is_(None))
    ).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    if expense.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if expense.status != "submitted":
        raise HTTPException(status_code=409, detail="Cannot delete a finalized expense")

    expense.deleted_at = datetime.now(timezone.utc)

    write_audit(
        db,
        expense_id=expense.id,
        actor_id=current_user.user_id,
        actor_role=current_user.role,
        action="soft_deleted",
        from_status="submitted",
        to_status="submitted",
        metadata=None,
    )
    db.commit()


@router.post("/api/v1/expenses/{id}/approve", response_model=ExpenseOut)
def approve_expense(
    id: str,
    body: StatusChangeRequest,
    current_user: AdminUser,
    db: DbSession,
) -> Expense:
    """Admin approves a submitted expense."""
    expense = db.scalars(
        select(Expense).where(Expense.id == id, Expense.deleted_at.is_(None))
    ).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    if expense.status != "submitted":
        raise HTTPException(status_code=409, detail="Expense is not in submitted status")

    old_status = expense.status
    expense.status = "approved"
    expense.reason = body.reason
    expense.updated_at = datetime.now(timezone.utc)

    write_audit(
        db,
        expense_id=expense.id,
        actor_id=current_user.user_id,
        actor_role=current_user.role,
        action="status_changed",
        from_status=old_status,
        to_status="approved",
        metadata={"reason": body.reason} if body.reason else None,
    )
    db.commit()
    db.refresh(expense)
    return expense


@router.post("/api/v1/expenses/{id}/reject", response_model=ExpenseOut)
def reject_expense(
    id: str,
    body: StatusChangeRequest,
    current_user: AdminUser,
    db: DbSession,
) -> Expense:
    """Admin rejects a submitted expense."""
    expense = db.scalars(
        select(Expense).where(Expense.id == id, Expense.deleted_at.is_(None))
    ).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    if expense.status != "submitted":
        raise HTTPException(status_code=409, detail="Expense is not in submitted status")

    old_status = expense.status
    expense.status = "rejected"
    expense.reason = body.reason
    expense.updated_at = datetime.now(timezone.utc)

    write_audit(
        db,
        expense_id=expense.id,
        actor_id=current_user.user_id,
        actor_role=current_user.role,
        action="status_changed",
        from_status=old_status,
        to_status="rejected",
        metadata={"reason": body.reason} if body.reason else None,
    )
    db.commit()
    db.refresh(expense)
    return expense


@router.get("/api/v1/expenses/{id}/audit", response_model=list[AuditEntry])
def get_expense_audit(
    id: str,
    current_user: AdminUser,
    db: DbSession,
) -> list[AuditLog]:
    """Get audit trail for an expense - admin only."""
    expense = db.scalars(select(Expense).where(Expense.id == id)).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    entries = db.scalars(
        select(AuditLog)
        .where(AuditLog.expense_id == id)
        .order_by(AuditLog.created_at.asc())
    ).all()
    return list(entries)
