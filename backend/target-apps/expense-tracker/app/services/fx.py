"""FX rate lookup service."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.fx_snapshot import FxSnapshot


class FXRateNotFound(Exception):
    """Raised when no FX snapshot exists for a given currency/date."""

    def __init__(self, currency: str, expense_date: date) -> None:
        self.currency = currency
        self.expense_date = expense_date
        super().__init__(f"No FX rate available for {currency} on {expense_date}")


def get_fx_rate(db: Session, currency: str, expense_date: date) -> Decimal:
    """Return rate_to_usd for a currency/date; raise FXRateNotFound if missing."""
    snapshot = db.scalars(
        select(FxSnapshot).where(
            FxSnapshot.currency == currency,
            FxSnapshot.date == expense_date,
        )
    ).first()
    if not snapshot:
        raise FXRateNotFound(currency, expense_date)
    return snapshot.rate_to_usd


def compute_amount_usd(amount: Decimal, rate_to_usd: Decimal) -> Decimal:
    """Compute USD value from amount and rate, rounded to 4 dp (stored), display to 2."""
    return (amount * rate_to_usd).quantize(Decimal("0.0001"))
