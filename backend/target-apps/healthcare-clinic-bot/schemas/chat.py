"""Chat schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class CreateSessionRequest(BaseModel):
    session_label: Optional[str] = None


class CreateSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    session_id: str
    created_at: datetime

    @field_validator("session_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v) if v is not None else v


class ChatMessageRequest(BaseModel):
    session_id: str
    message: str


class ChatMessageResponse(BaseModel):
    session_id: str
    reply: str
    disclaimer: str
    is_fallback: bool


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    role: str
    content: str
    is_fallback: bool
    created_at: datetime
