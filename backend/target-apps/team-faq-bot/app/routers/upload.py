"""POST /api/v1/upload — admin FAQ file upload."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import update

from app.config import get_settings
from app.dependencies import DbSession, require_admin_api_key
from app.models.faq_chunk import FaqChunk
from app.models.faq_collection import FaqCollection
from app.services.bedrock_client import get_bedrock_client
from app.services.faq_ingestion import chunk_sections, embed_sections, parse_faq_text
from schemas.upload import UploadResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload", response_model=UploadResponse, status_code=201)
def upload_faq(
    file: UploadFile,
    db: DbSession,
    _key: str = Depends(require_admin_api_key),
) -> UploadResponse:
    """Upload a plain-text FAQ file to replace the active collection."""
    settings = get_settings()

    # Read file content
    content = file.file.read()
    try:
        raw_text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be valid UTF-8 plain text.",
        )

    # Validate size
    char_count = len(raw_text)
    if char_count > settings.faq_max_chars:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum size of {settings.faq_max_chars} characters (got {char_count}).",
        )

    # Validate non-empty
    if not raw_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty or contains only whitespace.",
        )

    # Parse into sections
    sections = parse_faq_text(raw_text)
    chunks = chunk_sections(sections)

    # Embed sections
    bedrock = get_bedrock_client()
    embeddings = embed_sections(chunks, bedrock)

    # Transaction: deactivate old, insert new collection + chunks
    db.execute(
        update(FaqCollection).where(FaqCollection.is_active == True).values(is_active=False)  # noqa: E712
    )

    new_collection = FaqCollection(
        filename=file.filename or "unnamed.txt",
        raw_text=raw_text,
        char_count=char_count,
        uploaded_at=datetime.now(timezone.utc),
        is_active=True,
    )
    db.add(new_collection)
    db.flush()  # get id

    for chunk, embedding in zip(chunks, embeddings):
        vec_str = "[" + ",".join(str(float(x)) for x in embedding) + "]"
        db.add(FaqChunk(
            collection_id=new_collection.id,
            heading=chunk.heading,
            chunk_text=chunk.text,
            embedding=vec_str,
        ))

    db.commit()

    return UploadResponse(
        message=f"FAQ uploaded successfully. {len(chunks)} chunks created.",
        char_count=char_count,
    )
