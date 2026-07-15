"""Collections router — CRUD, documents (upload/list), and Q&A ask.

Routes:
  GET    /api/v1/collections
  POST   /api/v1/collections
  PATCH  /api/v1/collections/{id}
  POST   /api/v1/collections/{id}/documents
  GET    /api/v1/collections/{id}/documents
  POST   /api/v1/collections/{id}/ask
"""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import AuthUser, ContributorOrAdmin
from app.models.collection import Collection
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.audit_service import log_audit_event
from app.services.bedrock_client import get_bedrock_client
from app.services.prompts import build_qa_prompt
from schemas.collections import CollectionCreate, CollectionOut, CollectionUpdate
from schemas.documents import DocumentOut
from schemas.qa import AskRequest, AskResponse, Citation

router = APIRouter()

ALLOWED_MIMES = {
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


# ── Collections CRUD ──

@router.get("/api/v1/collections", response_model=list[CollectionOut])
def list_collections(
    current_user: AuthUser,
    db: Session = Depends(get_db),
) -> list[CollectionOut]:
    """All roles can list collections."""
    rows = db.scalars(select(Collection).order_by(Collection.name)).all()
    return [CollectionOut.model_validate(r) for r in rows]


@router.post("/api/v1/collections", response_model=CollectionOut, status_code=201)
def create_collection(
    body: CollectionCreate,
    current_user: ContributorOrAdmin,
    db: Session = Depends(get_db),
) -> CollectionOut:
    """Contributor/admin can create."""
    existing = db.scalars(select(Collection).where(Collection.name == body.name)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Collection name already exists")
    coll = Collection(
        name=body.name,
        description=body.description,
        created_by=current_user.user_id,
    )
    db.add(coll)
    db.commit()
    db.refresh(coll)
    return CollectionOut.model_validate(coll)


@router.patch("/api/v1/collections/{id}", response_model=CollectionOut)
def update_collection(
    id: str,
    body: CollectionUpdate,
    current_user: ContributorOrAdmin,
    db: Session = Depends(get_db),
) -> CollectionOut:
    """Contributor/admin can update."""
    coll = db.scalars(select(Collection).where(Collection.id == id)).first()
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    updates = body.model_dump(exclude_unset=True)
    if "name" in updates:
        dup = db.scalars(select(Collection).where(Collection.name == updates["name"], Collection.id != id)).first()
        if dup:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Collection name already exists")
    for k, v in updates.items():
        setattr(coll, k, v)
    db.commit()
    db.refresh(coll)
    return CollectionOut.model_validate(coll)


# ── Documents ──

@router.get("/api/v1/collections/{id}/documents", response_model=list[DocumentOut])
def list_documents(
    id: str,
    current_user: AuthUser,
    db: Session = Depends(get_db),
) -> list[DocumentOut]:
    """All roles can list documents in a collection."""
    coll = db.scalars(select(Collection).where(Collection.id == id)).first()
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    rows = db.scalars(
        select(Document).where(Document.collection_id == id).order_by(Document.uploaded_at.desc())
    ).all()
    results = []
    for doc in rows:
        d = DocumentOut(
            id=str(doc.id),
            filename=doc.filename,
            status=doc.status,
            uploaded_at=str(doc.uploaded_at) if doc.uploaded_at else None,
            uploader=None,
        )
        results.append(d)
    return results


@router.post("/api/v1/collections/{id}/documents", response_model=DocumentOut, status_code=201)
def upload_document(
    id: str,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    current_user: ContributorOrAdmin,
    db: Session = Depends(get_db),
) -> DocumentOut:
    """Upload a document to a collection."""
    coll = db.scalars(select(Collection).where(Collection.id == id)).first()
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")

    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIMES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type: {content_type}. Allowed: PDF, TXT, DOCX.",
        )

    file_bytes = file.file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File exceeds 20 MB limit.",
        )

    settings = get_settings()
    os.makedirs(settings.pdf_storage_dir, exist_ok=True)
    doc_id = str(uuid.uuid4())
    file_path = os.path.join(settings.pdf_storage_dir, f"{doc_id}_{file.filename}")
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    doc = Document(
        id=doc_id,
        collection_id=id,
        filename=file.filename or "untitled",
        file_type=content_type,
        status="waiting",
        uploaded_by=current_user.user_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    log_audit_event(
        db=db,
        user_id=current_user.user_id,
        role=current_user.role,
        action_type="upload",
        resource_type="document",
        resource_id=doc.id,
        resource_name=doc.filename,
        outcome="success",
    )

    background_tasks.add_task(_process_document, doc.id, file_path)

    return DocumentOut(
        id=str(doc.id),
        filename=doc.filename,
        status=doc.status,
        uploaded_at=str(doc.uploaded_at) if doc.uploaded_at else None,
        uploader=current_user.username,
    )


# ── Q&A / Ask ──

@router.post("/api/v1/collections/{id}/ask", response_model=AskResponse)
def ask_question(
    id: str,
    body: AskRequest,
    current_user: AuthUser,
    db: Session = Depends(get_db),
) -> AskResponse:
    """Ask a question against a collection's documents."""
    coll = db.scalars(select(Collection).where(Collection.id == id)).first()
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")

    doc_ids = list(db.scalars(
        select(Document.id).where(
            Document.collection_id == id,
            Document.status == "ready",
        )
    ).all())

    if not doc_ids:
        log_audit_event(
            db=db,
            user_id=current_user.user_id,
            role=current_user.role,
            action_type="qa_query",
            resource_type="collection",
            resource_id=id,
            resource_name=coll.name,
            outcome="not_found",
            question_excerpt=body.question[:100],
        )
        return AskResponse(answer="Not found in documents", citations=[])

    bedrock = get_bedrock_client()
    query_embedding = bedrock.invoke_embed(body.question)
    chunks = _retrieve_chunks(db, doc_ids, query_embedding)

    if not chunks:
        log_audit_event(
            db=db,
            user_id=current_user.user_id,
            role=current_user.role,
            action_type="qa_query",
            resource_type="collection",
            resource_id=id,
            resource_name=coll.name,
            outcome="not_found",
            question_excerpt=body.question[:100],
        )
        return AskResponse(answer="Not found in documents", citations=[])

    context_texts = [(c.chunk_text, c.document.filename if c.document else "unknown") for c in chunks]
    prompt = build_qa_prompt(body.question, context_texts)
    answer_text = bedrock.invoke_text(prompt)

    if "not found in documents" in answer_text.lower():
        outcome = "not_found"
        citations: list[Citation] = []
    else:
        outcome = "cited_answer"
        citations = [
            Citation(filename=fname, snippet=text[:200])
            for text, fname in context_texts
        ]

    log_audit_event(
        db=db,
        user_id=current_user.user_id,
        role=current_user.role,
        action_type="qa_query",
        resource_type="collection",
        resource_id=id,
        resource_name=coll.name,
        outcome=outcome,
        question_excerpt=body.question[:100],
    )

    return AskResponse(answer=answer_text, citations=citations)


def _retrieve_chunks(db: Session, doc_ids: list[str], query_embedding: list[float]) -> list:
    """Retrieve top-k relevant chunks."""
    from app.config import get_settings
    settings = get_settings()
    top_k = settings.retrieval_top_k
    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id.in_(doc_ids))
        .limit(top_k)
    )
    chunks = list(db.scalars(stmt).all())
    for c in chunks:
        _ = c.document
    return chunks


def _process_document(doc_id: str, file_path: str) -> None:
    """Background task: extract text, chunk, embed, mark ready."""
    from app.database import SessionLocal
    from app.models.document_chunk import DocumentChunk as DC
    from app.services.ingestion import extract_and_chunk

    session = SessionLocal()
    try:
        doc = session.scalars(select(Document).where(Document.id == doc_id)).first()
        if not doc:
            return
        doc.status = "processing"
        session.commit()

        try:
            chunks = extract_and_chunk(file_path, doc.file_type)
            for idx, chunk_text in enumerate(chunks):
                chunk = DC(
                    document_id=doc_id,
                    chunk_index=idx,
                    chunk_text=chunk_text,
                )
                session.add(chunk)
            doc.status = "ready"
            session.commit()
        except Exception as exc:
            doc.status = "failed"
            doc.error_message = str(exc)[:500]
            session.commit()
    finally:
        session.close()
