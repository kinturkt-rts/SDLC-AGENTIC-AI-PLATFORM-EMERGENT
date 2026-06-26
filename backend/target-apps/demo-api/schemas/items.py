"""Pydantic schemas for the /items endpoint."""

from pydantic import BaseModel, Field


class Item(BaseModel):
    """A single item returned by the demo-api items endpoint."""

    id: int = Field(..., description="Stable identifier for the item.", ge=1)
    name: str = Field(..., description="Human-readable item name.", min_length=1)
