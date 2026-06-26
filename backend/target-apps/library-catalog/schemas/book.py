from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator


class BookBase(BaseModel):
    isbn: str
    title: str
    author: str
    total_copies: int


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    total_copies: Optional[int] = None


class BookResponse(BookBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    created_at: datetime
    available_copies: Optional[int] = None  # Computed field

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v