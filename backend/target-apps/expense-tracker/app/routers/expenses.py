"""Expenses router — CRUD, approve/reject, audit log."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import Actor, AuthActor, require_role
from app.models.expense import Expense
from app.models.audit_log import AuditLog
from app.models.fx_rate_snapshot import FxRateSnapshot

from schemas.expenses import (
    ExpenseCreate,
    ExpenseUpdate,
    ExpenseOut,
    PagedExpenses,
    AuditEntry,
)

router = APIRouter()


def _compute_usd(db: Session, currency: str, expense_date, original_amount: Decimal) -> Decimal:
    """Look up FX rate and compute USD amount. Raises 422 if no rate found."""
    rate_row = db.scalars(
        select(FxRateSnapshot).where(
            FxRateSnapshot.currency == currency,
            FxRateSnapshot.rate_date == expense_date,
        )
    ).first()
    if not rate_row:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No FX rate available for currency={currency} on date={expense_date}",
        )
    usd_rate = Decimal(str(rate_row.usd_rate))
    usd_amount = (original_amount * usd_rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return usd_amount


@router.post("/api/v1/expenses", response_model=ExpenseOut, status_code=201)
def create_expense(
    body: ExpenseCreate,
    actor: AuthActor,
    db: Session = Depends(get_db),
) -> Expense:
    """FR-1: Submit an expense (employee only)."""
    if actor.role != "employee":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only employees can submit expenses")

    usd_amount = _compute_usd(db, body.currency, body.expense_date, body.amount)

    team_id = actor.team_ids[0] if actor.team_ids else None
    if team_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Employee has no team assigned")

    expense = Expense(
        employee_id=actor.id,
        team_id=team_id,
        original_amount=body.amount,
        currency=body.currency,
        usd_amount=usd_amount,
        category=body.category,
        description=body.description,
        expense_date=body.expense_date,
        status="submitted",
    )
    db.add(expense)
    db.flush()

    audit = AuditLog(
        expense_id=expense.id,
        from_status=None,
        to_status="submitted",
        actor_id=actor.id,
        actor_role=actor.role,
    )
    db.add(audit)
    db.commit()
    db.refresh(expense)
    return expense


@router.patch("/api/v1/expenses/{id}", response_model=ExpenseOut)
def update_expense(
    id: int,
    body: ExpenseUpdate,
    actor: AuthActor,
    db: Session = Depends(get_db),
) -> Expense:
    """FR-3: Edit expense (submitted only, owner only)."""
    if actor.role != "employee":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only employees can edit expenses")

    expense = db.scalars(select(Expense).where(Expense.id == id, Expense.deleted_at.is_(None))).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    if expense.employee_id != actor.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit another employee's expense")
    if expense.status != "submitted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only submitted expenses can be edited")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return expense

    if "amount" in updates:
        expense.original_amount = updates["amount"]
    if "currency" in updates:
        expense.currency = updates["currency"]
    if "category" in updates:
        expense.category = updates["category"]
    if "description" in updates:
        expense.description = updates["description"]
    if "expense_date" in updates:
        expense.expense_date = updates["expense_date"]

    expense.usd_amount = _compute_usd(
        db, expense.currency, expense.expense_date, Decimal(str(expense.original_amount))
    )
    expense.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/api/v1/expenses/{id}", status_code=204, response_model=None)
def delete_expense(
    id: int,
    actor: AuthActor,
    db: Session = Depends(get_db),
) -> None:
    """FR-8: Soft delete (submitted only, owner only)."""
    if actor.role != "employee":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only employees can delete expenses")

    expense = db.scalars(select(Expense).where(Expense.id == id, Expense.deleted_at.is_(None))).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    if expense.employee_id != actor.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete another employee's expense")
    if expense.status != "submitted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only submitted expenses can be deleted")

    expense.deleted_at = datetime.now(timezone.utc)
    db.commit()


@router.get("/api/v1/expenses", response_model=PagedExpenses)
def list_expenses(
    actor: AuthActor,
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    category: Optional[str] = Query(default=None),
    year: Optional[int] = Query(default=None),
    month: Optional[int] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PagedExpenses:
    """FR-10: List own expenses with filters (employee only)."""
    if actor.role != "employee":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only employees can list their own expenses")

    base = select(Expense).where(
        Expense.employee_id == actor.id,
        Expense.deleted_at.is_(None),
    )
    if status_filter:
        base = base.where(Expense.status == status_filter)
    if category:
        base = base.where(Expense.category == category)
    if year:
        base = base.where(func.extract("year", Expense.expense_date) == year)
    if month:
        base = base.where(func.extract("month", Expense.expense_date) == month)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(db.scalars(base.offset(offset).limit(limit)).all())
    return PagedExpenses(items=rows, total=total, limit=limit, offset=offset)


@router.get("/api/v1/expenses/{id}", response_model=ExpenseOut)
def get_expense(
    id: int,
    actor: AuthActor,
    db: Session = Depends(get_db),
) -> Expense:
    """Get a single expense (owner or admin)."""
    expense = db.scalars(select(Expense).where(Expense.id == id, Expense.deleted_at.is_(None))).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    if actor.role == "employee" and expense.employee_id != actor.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return expense


@router.get("/api/v1/expenses/{id}/audit-log", response_model=list[AuditEntry])
def get_expense_audit_log(
    id: int,
    actor: AuthActor,
    db: Session = Depends(get_db),
) -> list[AuditLog]:
    """FR-5: Audit log for an expense."""
    expense = db.scalars(select(Expense).where(Expense.id == id)).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    if actor.role == "employee" and expense.employee_id != actor.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    entries = list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.expense_id == id)
            .order_by(AuditLog.occurred_at)
        ).all()
    )
    return entries


@router.post("/api/v1/expenses/{id}/approve", response_model=ExpenseOut)
def approve_expense(
    id: int,
    actor: Actor = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> Expense:
    """FR-4: Approve (admin only)."""
    expense = db.scalars(select(Expense).where(Expense.id == id, Expense.deleted_at.is_(None))).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    if expense.status != "submitted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only submitted expenses can be approved")

    expense.status = "approved"
    expense.updated_at = datetime.now(timezone.utc)

    audit = AuditLog(
        expense_id=expense.id,
        from_status="submitted",
        to_status="approved",
        actor_id=actor.id,
        actor_role=actor.role,
    )
    db.add(audit)
    db.commit()
    db.refresh(expense)
    return expense


@router.post("/api/v1/expenses/{id}/reject", response_model=ExpenseOut)
def reject_expense(
    id: int,
    actor: Actor = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> Expense:
    """FR-4: Reject (admin only)."""
    expense = db.scalars(select(Expense).where(Expense.id == id, Expense.deleted_at.is_(None))).first()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    if expense.status != "submitted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only submitted expenses can be rejected")

    expense.status = "rejected"
    expense.updated_at = datetime.now(timezone.utc)

    audit = AuditLog(
        expense_id=expense.id,
        from_status="submitted",
        to_status="rejected",
        actor_id=actor.id,
        actor_role=actor.role,
    )
    db.add(audit)
    db.commit()
    db.refresh(expense)
    return expense
