from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.pg_types import document_status_column, DocumentStatus


class Document(Base):
    __tablename__ = "documents"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    collection_id: Mapped[int] = mapped_column(Integer, ForeignKey("collections.id"), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(document_status_column(), nullable=False, default=DocumentStatus.pending)
    uploaded_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    collection = relationship("Collection", back_populates="documents")
    uploader = relationship("User", back_populates="uploaded_documents")
    chunks = relationship("DocumentChunk", back_populates="document")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = Column("embedding", Text)  # Will be VECTOR(1024) on Postgres, TEXT on SQLite
    page_number: Mapped[int] = mapped_column(Integer, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    document = relationship("Document", back_populates="chunks")
