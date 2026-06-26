from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional
from app.models.pg_types import DocumentStatus


class DocumentSummary(BaseModel):
    id: int
    title: str
    status: DocumentStatus
    uploaded_by: int
    chunk_count: int = Field(default=0, description="Number of processed chunks")
    created_at: datetime
    
    class Config:
        from_attributes = True


class Document(BaseModel):
    id: int
    title: str
    file_path: str
    collection_id: int
    status: DocumentStatus
    uploaded_by: int
    created_at: datetime
    
    class Config:
        from_attributes = True
