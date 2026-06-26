"""FAQ schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class FaqCreate(BaseModel):
    category: str
    question: str
    answer: str


class FaqUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


class FaqOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category: str
    question: str
    answer: str
    is_active: bool
