from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON
from app.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collection_id: Mapped[int] = mapped_column(Integer, ForeignKey("collections.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    collection = relationship("Collection", back_populates="chat_sessions")
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_user: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=True)
    citations = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")
