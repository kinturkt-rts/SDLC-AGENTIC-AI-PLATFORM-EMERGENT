from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional
from app.models.pg_types import CollectionMemberRole


class CreateCollection(BaseModel):
    name: str = Field(..., description="Collection name", max_length=255)
    description: Optional[str] = Field(None, description="Collection description")


class CollectionSummary(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    archived: bool
    document_count: int = Field(default=0, description="Number of documents in collection")
    user_role: CollectionMemberRole = Field(..., description="User's role in this collection")
    created_at: datetime
    
    class Config:
        from_attributes = True


class Collection(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    owner_id: int
    archived: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class AddMember(BaseModel):
    user_id: int = Field(..., description="User ID to add")
    role: CollectionMemberRole = Field(..., description="Role to assign")


class Membership(BaseModel):
    id: int
    collection_id: int
    user_id: int
    role: CollectionMemberRole
    created_at: datetime
    
    class Config:
        from_attributes = True
