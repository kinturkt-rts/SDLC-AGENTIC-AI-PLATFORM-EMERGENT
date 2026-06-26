from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator


class LoanCreate(BaseModel):
    book_id: str


class LoanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    book_id: str
    member_id: str
    checkout_at: datetime
    due_at: datetime
    returned_at: Optional[datetime] = None
    is_overdue: Optional[bool] = None  # Computed field

    @field_validator("id", "book_id", "member_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v