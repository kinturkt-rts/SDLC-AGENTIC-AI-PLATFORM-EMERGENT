"""Stock-adjustment service (FR-7, NFR-6).

Wraps `SELECT FOR UPDATE` on the product row, the `qty_on_hand` update, and
the `stock_movements` insert in a single DB transaction. If the resulting
quantity would be negative we raise `NegativeStockError`, the route handler
translates that into HTTP 422, and the transaction is rolled back so neither
row is mutated.

`SELECT FOR UPDATE` is only emitted on Postgres; SQLite (used as the test
fallback) silently degrades — correctness still holds because each test runs
single-threaded.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.stock_movement import StockMovement


class NegativeStockError(ValueError):
    """Raised when an adjust-stock would drive `qty_on_hand` below zero."""


class ProductNotFoundError(LookupError):
    """Raised when the target product does not exist."""


class InvalidDeltaError(ValueError):
    """Raised when `delta == 0` (FR-7 implies non-zero movements)."""


@dataclass(frozen=True)
class AdjustStockResult:
    movement: StockMovement
    new_qty: int


def adjust_stock(
    db: Session,
    *,
    product_id: uuid.UUID,
    delta: int,
    reason: str,
    note: str | None,
    performed_by: uuid.UUID,
) -> AdjustStockResult:
    """Atomic stock adjustment — see module docstring."""
    if delta == 0:
        raise InvalidDeltaError("delta must be non-zero")

    # Lock the product row when on Postgres; on SQLite the `with_for_update`
    # call is a no-op via dialect handling but we guard explicitly for safety.
    stmt = select(Product).where(Product.id == product_id)
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()
    product = db.execute(stmt).scalar_one_or_none()
    if product is None:
        raise ProductNotFoundError(str(product_id))

    new_qty = product.qty_on_hand + delta
    if new_qty < 0:
        raise NegativeStockError(
            f"qty_on_hand would become {new_qty}; current={product.qty_on_hand}, delta={delta}"
        )

    product.qty_on_hand = new_qty
    movement = StockMovement(
        product_id=product.id,
        delta=delta,
        reason=reason,
        note=note,
        performed_by=performed_by,
    )
    db.add(movement)
    db.flush()  # surface DB errors before commit
    db.commit()
    db.refresh(movement)
    db.refresh(product)
    return AdjustStockResult(movement=movement, new_qty=product.qty_on_hand)
