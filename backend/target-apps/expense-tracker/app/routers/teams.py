"""Teams router — CRUD and monthly report."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import Actor, AuthActor, require_role
from app.models.team import Team
from app.models.expense import Expense

from schemas.teams import TeamCreate, TeamOut, ReportOut, CategoryTotal

router = APIRouter()


@router.post("/api/v1/teams", response_model=TeamOut, status_code=201)
def create_team(
    body: TeamCreate,
    actor: Actor = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> Team:
    """FR-7: Create a team (admin only)."""
    existing = db.scalars(select(Team).where(Team.name == body.name)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Team name already exists")
    team = Team(name=body.name)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.get("/api/v1/teams", response_model=list[TeamOut])
def list_teams(
    actor: Actor = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> list[Team]:
    """FR-7: List teams (admin only)."""
    return list(db.scalars(select(Team).where(Team.deleted_at.is_(None))).all())


@router.get("/api/v1/teams/{team_id}/report", response_model=ReportOut)
def team_report(
    team_id: int,
    actor: AuthActor,
    db: Session = Depends(get_db),
    year: int = Query(...),
    month: int = Query(...),
) -> ReportOut:
    """FR-6: Monthly team aggregation report (manager scoped to team)."""
    if actor.role == "manager":
        if team_id not in actor.team_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this team")
    elif actor.role == "admin":
        pass
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    team = db.scalars(select(Team).where(Team.id == team_id, Team.deleted_at.is_(None))).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    rows = db.execute(
        select(
            Expense.category,
            func.sum(Expense.usd_amount).label("total"),
        )
        .where(
            Expense.team_id == team_id,
            Expense.status == "approved",
            Expense.deleted_at.is_(None),
            func.extract("year", Expense.expense_date) == year,
            func.extract("month", Expense.expense_date) == month,
        )
        .group_by(Expense.category)
    ).all()

    categories = []
    grand_total = Decimal("0")
    for row in rows:
        total_val = Decimal(str(row.total)) if row.total else Decimal("0")
        categories.append(CategoryTotal(category=row.category, total=total_val))
        grand_total += total_val

    return ReportOut(
        team_id=team_id,
        year=year,
        month=month,
        categories=categories,
        grand_total=grand_total,
    )
