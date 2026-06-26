from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator


class HoldCreate(BaseModel):
    book_id: str


class HoldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    book_id: str
    member_id: str
    placed_at: datetime
    fulfilled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    queue_position: Optional[int] = None  # Computed field

    @field_validator("id", "book_id", "member_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v