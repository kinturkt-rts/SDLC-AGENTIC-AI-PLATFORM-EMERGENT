"""Stock movement DTOs (FR-7/8)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Mirrors `inventory_app.movement_reason` — keep in sync with the DB enum.
MovementReasonLiteral = Literal["sale", "restock", "adjustment"]


class AdjustStockRequest(BaseModel):
    """Body for `POST /products/{id}/adjust-stock` (FR-7)."""

    delta: int = Field(..., description="Signed change in qty_on_hand. Cannot be 0.")
    reason: MovementReasonLiteral
    note: str | None = Field(None, max_length=500)


class MovementOut(BaseModel):
    """Stock movement record for history endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    delta: int
    reason: str
    note: str | None
    performed_by: uuid.UUID | None
    created_at: datetime


class AdjustStockResponse(BaseModel):
    """Response for adjust-stock — returns the new movement plus updated qty."""

    model_config = ConfigDict(from_attributes=True)

    movement: MovementOut
    qty_on_hand: int
