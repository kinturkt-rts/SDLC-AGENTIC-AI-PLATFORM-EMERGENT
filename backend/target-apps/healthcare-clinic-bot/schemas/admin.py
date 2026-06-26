"""Admin schemas."""
from pydantic import BaseModel


class AdminStats(BaseModel):
    total_faqs: int
    total_sessions: int
    total_messages: int
    fallback_rate: float
