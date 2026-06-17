"""Common HTTP DTOs — pagination envelope used by all list endpoints (FR-6/8)."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Uniform list-response shape: `{items, total, limit, offset}`."""

    model_config = ConfigDict(from_attributes=True)

    items: list[T]
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)
