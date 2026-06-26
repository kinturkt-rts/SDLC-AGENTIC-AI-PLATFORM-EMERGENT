from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ChatRequest(BaseModel):
    message: str = Field(..., description="User question")
    session_id: Optional[int] = Field(None, description="Existing session ID for continuing conversation")


class Citation(BaseModel):
    document_title: str = Field(..., description="Source document title")
    page_number: Optional[int] = Field(None, description="Page number if available")
    confidence: float = Field(..., description="Confidence score for this citation")
    content_preview: str = Field(..., description="Preview of matching content")


class ChatResponse(BaseModel):
    answer: str = Field(..., description="Generated answer or refusal message")
    confidence: float = Field(..., description="Overall confidence score")
    citations: List[Citation] = Field(default=[], description="Supporting document citations")
    session_id: int = Field(..., description="Session ID for this conversation")
    refused: bool = Field(default=False, description="True if answer was refused due to low confidence")


class ChatMessage(BaseModel):
    id: int
    content: str
    is_user: bool
    confidence_score: Optional[float] = None
    citations: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
