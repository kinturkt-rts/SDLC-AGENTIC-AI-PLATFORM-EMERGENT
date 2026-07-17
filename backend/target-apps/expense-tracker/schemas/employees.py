"""Pydantic schemas for employees endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class EmployeeTeamUpdate(BaseModel):
    team_id: int


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    team_id: Optional[int] = None
    role: str
    created_at: Optional[datetime] = None
