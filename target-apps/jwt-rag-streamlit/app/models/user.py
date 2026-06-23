import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.pg_types import user_role_column, user_status_column, UserRole, UserStatus


class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(user_role_column(), nullable=False)
    status: Mapped[UserStatus] = mapped_column(user_status_column(), nullable=False, default=UserStatus.active)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    owned_collections = relationship("Collection", back_populates="owner")
    collection_memberships = relationship("CollectionMembership", back_populates="user")
    uploaded_documents = relationship("Document", back_populates="uploader")
    chat_sessions = relationship("ChatSession", back_populates="user")
    audit_entries = relationship("AuditLog", back_populates="user")
