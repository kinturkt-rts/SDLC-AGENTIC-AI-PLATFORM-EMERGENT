"""Teams management and summary routes."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.dependencies import AdminUser, AuthUser, DbSession
from app.models.expense import Expense
from app.models.team import Team
from app.models.user import User
from app.schemas.summary import CategoryTotal, SummaryOut
from app.schemas.team import MemberAction, TeamCreate, TeamOut
from app.schemas.user import UserOut

router = APIRouter(tags=["teams"])


@router.post("/api/v1/teams", response_model=TeamOut, status_code=201)
def create_team(
    body: TeamCreate,
    current_user: AdminUser,
    db: DbSession,
) -> Team:
    """Create a new team \u2014 admin only."""
    existing = db.scalars(select(Team).where(Team.name == body.name, Team.deleted_at.is_(None))).first()
    if existing:
        raise HTTPException(status_code=409, detail="Team name already exists")

    team = Team(name=body.name, description=body.description)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.get("/api/v1/teams", response_model=list[TeamOut])
def list_teams(
    current_user: AuthUser,
    db: DbSession,
) -> list[Team]:
    """List teams \u2014 admin or manager."""
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Forbidden")

    teams = db.scalars(select(Team).where(Team.deleted_at.is_(None)).order_by(Team.name)).all()
    return list(teams)


@router.patch("/api/v1/teams/{team_id}/members", response_model=UserOut)
def manage_team_members(
    team_id: str,
    body: MemberAction,
    current_user: AdminUser,
    db: DbSession,
) -> User:
    """Assign or remove a user from a team \u2014 admin only."""
    team = db.scalars(select(Team).where(Team.id == team_id, Team.deleted_at.is_(None))).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    user = db.scalars(select(User).where(User.id == body.user_id, User.deleted_at.is_(None))).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.action == "assign":
        user.team_id = team_id
    elif body.action == "remove":
        user.team_id = None

    db.commit()
    db.refresh(user)
    return user


@router.get("/api/v1/teams/{team_id}/expenses/summary", response_model=SummaryOut)
def team_expense_summary(
    team_id: str,
    current_user: AuthUser,
    db: DbSession,
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
) -> dict:
    """Monthly expense summary by category for a team \u2014 manager/admin only."""
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Forbidden")

    # Verify team exists
    team = db.scalars(select(Team).where(Team.id == team_id, Team.deleted_at.is_(None))).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    from datetime import date

    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    stmt = (
        select(Expense.category, func.sum(Expense.amount_usd).label("total_usd"))
        .where(
            Expense.team_id == team_id,
            Expense.status == "approved",
            Expense.deleted_at.is_(None),
            Expense.expense_date >= start_date,
            Expense.expense_date < end_date,
        )
        .group_by(Expense.category)
    )

    rows = db.execute(stmt).all()
    categories = []
    grand_total = Decimal("0")
    for row in rows:
        total = row.total_usd or Decimal("0")
        categories.append(CategoryTotal(category=row.category, total_usd=total))
        grand_total += total

    return {
        "team_id": team_id,
        "year": year,
        "month": month,
        "categories": categories,
        "grand_total_usd": grand_total,
    }
