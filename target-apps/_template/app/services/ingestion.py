"""PDF ingestion for the local pgvector RAG pattern.

Pipeline: persist raw PDF bytes → extract text per page → chunk → embed each
chunk via Bedrock Titan → store chunks + vectors in Postgres (pgvector).

Used only when design specifies document Q&A with pgvector retrieval. The
developer-agent mirrors the `document_chunks` table written by database-agent;
column names below must match that schema.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from app.config import settings
from app.services.bedrock_client import BedrockClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Chunk:
    """A single text chunk ready to embed and store."""

    page: int
    text: str


def save_pdf_bytes(doc_id: str, filename: str, content: bytes) -> str:
    """Persist raw PDF bytes to local storage (MVP — no S3). Returns the path."""
    storage = Path(settings.pdf_storage_dir)
    storage.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name
    target = storage / f"{doc_id}-{safe_name}"
    target.write_bytes(content)
    return str(target)


def extract_pages(content: bytes) -> list[tuple[int, str]]:
    """Return [(page_number, text)] for each page with extractable text."""
    import io

    reader = PdfReader(io.BytesIO(content))
    pages: list[tuple[int, str]] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append((idx, text))
    return pages


def chunk_text(page: int, text: str) -> list[Chunk]:
    """Split one page into overlapping word-window chunks."""
    size = settings.chunk_size
    overlap = settings.chunk_overlap
    words = text.split()
    if not words:
        return []
    chunks: list[Chunk] = []
    start = 0
    step = max(size - overlap, 1)
    while start < len(words):
        window = words[start : start + size]
        chunks.append(Chunk(page=page, text=" ".join(window)))
        start += step
    return chunks


def build_chunks(content: bytes) -> list[Chunk]:
    """Extract and chunk an entire PDF."""
    chunks: list[Chunk] = []
    for page, text in extract_pages(content):
        chunks.extend(chunk_text(page, text))
    return chunks


def embed_chunks(chunks: list[Chunk], bedrock: BedrockClient) -> list[list[float]]:
    """Embed every chunk; one Titan call per chunk (batch later if needed)."""
    return [bedrock.invoke_embedding(c.text) for c in chunks]
