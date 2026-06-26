import os
from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.dependencies import DbSession, CurrentUser, get_user_collection_access
from app.models.document import Document, DocumentChunk
from app.models.collection import Collection
from app.models.pg_types import CollectionMemberRole, DocumentStatus
from app.services.audit import log_audit_event
from app.services.ingestion import save_pdf_file, process_document_ingestion
from schemas.document import DocumentSummary, Document as DocumentSchema

router = APIRouter()


@router.get("/{collection_id}/documents", response_model=List[DocumentSummary])
def list_documents(collection_id: int, current_user: CurrentUser, db: DbSession):
    """List documents in a collection"""
    # Check collection access
    get_user_collection_access(db, current_user, collection_id)
    
    # Get documents with chunk counts
    query = db.query(
        Document,
        func.coalesce(func.count(DocumentChunk.id), 0).label('chunk_count')
    ).outerjoin(DocumentChunk, Document.id == DocumentChunk.document_id)
    
    query = query.filter(Document.collection_id == collection_id)
    query = query.group_by(Document.id).order_by(Document.created_at.desc())
    
    results = []
    for document, chunk_count in query.all():
        results.append(DocumentSummary(
            id=document.id,
            title=document.title,
            status=document.status,
            uploaded_by=document.uploaded_by,
            chunk_count=chunk_count or 0,
            created_at=document.created_at
        ))
    
    return results


@router.post("/{collection_id}/documents", response_model=DocumentSchema, status_code=201)
def upload_document(
    collection_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
    title: str = Form(...)
):
    """Upload PDF document to collection"""
    # Check collection access (need contributor role)
    user_role = get_user_collection_access(db, current_user, collection_id)
    if user_role != CollectionMemberRole.contributor:
        raise HTTPException(status_code=403, detail="Contributor access required to upload documents")
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Check file size (10MB limit)
    max_size = 10 * 1024 * 1024  # 10MB
    file_content = file.file.read()
    if len(file_content) > max_size:
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
    
    # Save file
    try:
        file_path = save_pdf_file(file_content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Create document record
    document = Document(
        title=title,
        file_path=file_path,
        collection_id=collection_id,
        status=DocumentStatus.pending,
        uploaded_by=current_user.id
    )
    
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # Log upload
    log_audit_event(
        db=db,
        user_id=current_user.id,
        action="document_uploaded",
        resource_type="document",
        resource_id=document.id,
        details={"title": title, "filename": file.filename, "collection_id": collection_id},
        ip_address=request.client.host if request.client else None
    )
    
    # Process document in background
    background_tasks.add_task(process_document_ingestion, db, document)
    
    return document


@router.delete("/{collection_id}/documents/{document_id}", status_code=204)
def delete_document(
    collection_id: int,
    document_id: int,
    request: Request,
    current_user: CurrentUser,
    db: DbSession
):
    """Delete document from collection"""
    # Check collection access (need contributor role)
    user_role = get_user_collection_access(db, current_user, collection_id)
    if user_role != CollectionMemberRole.contributor:
        raise HTTPException(status_code=403, detail="Contributor access required to delete documents")
    
    # Get document
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.collection_id == collection_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete file from storage
    try:
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
    except Exception as e:
        print(f"Warning: Failed to delete file {document.file_path}: {e}")
    
    # Delete document chunks first (foreign key constraint)
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
    
    # Delete document
    db.delete(document)
    db.commit()
    
    # Log deletion
    log_audit_event(
        db=db,
        user_id=current_user.id,
        action="document_deleted",
        resource_type="document",
        resource_id=document_id,
        details={"title": document.title, "collection_id": collection_id},
        ip_address=request.client.host if request.client else None
    )
