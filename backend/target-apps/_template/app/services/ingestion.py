"""Document ingestion for the local pgvector RAG pattern.

Pipeline: persist raw bytes → extract text per page/section → chunk → embed
each chunk via Bedrock Titan → store chunks + vectors in Postgres (pgvector).

Supports the file types the upload UI actually accepts: PDF, DOCX, and plain
text (.txt/.md/.log). Do not add a format here without a matching extractor —
`extract_pages` raises `UnsupportedDocumentTypeError` for anything else so a
failed upload surfaces a clear reason instead of silently producing zero
chunks.

Used only when design specifies document Q&A with pgvector retrieval. The
developer-agent mirrors the `document_chunks` table written by database-agent;
column names below must match that schema.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from app.config import get_settings
from app.services.bedrock_client import BedrockClient

logger = logging.getLogger(__name__)

_TEXT_EXTENSIONS = {"txt", "text", "md", "markdown", "log", "rst", "csv"}


class UnsupportedDocumentTypeError(ValueError):
    """Raised when a document's extension has no matching text extractor."""


@dataclass(frozen=True)
class Chunk:
    """A single text chunk ready to embed and store."""

    page: int
    text: str


def save_pdf_bytes(doc_id: str, filename: str, content: bytes) -> str:
    """Persist raw uploaded bytes to local storage (MVP — no S3). Returns the path."""
    storage = Path(get_settings().pdf_storage_dir)
    storage.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name
    target = storage / f"{doc_id}-{safe_name}"
    target.write_bytes(content)
    return str(target)


def _extract_pdf_pages(content: bytes) -> list[tuple[int, str]]:
    import io

    reader = PdfReader(io.BytesIO(content))
    pages: list[tuple[int, str]] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append((idx, text))
    return pages


def _extract_docx_pages(content: bytes) -> list[tuple[int, str]]:
    import io

    from docx import Document as DocxDocument

    doc = DocxDocument(io.BytesIO(content))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [(1, text.strip())] if text.strip() else []


def _extract_text_pages(content: bytes) -> list[tuple[int, str]]:
    text = content.decode("utf-8", errors="replace").strip()
    return [(1, text)] if text else []


def extract_pages(content: bytes, filename: str = "") -> list[tuple[int, str]]:
    """Return [(page_number, text)] for each page/section with extractable text.

    Dispatches on the filename extension. Raises `UnsupportedDocumentTypeError`
    for extensions with no extractor — callers must catch this and mark the
    document as failed with a clear reason rather than leaving it stuck in
    "processing" forever.
    """
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext == "pdf" or not ext:
        return _extract_pdf_pages(content)
    if ext == "docx":
        return _extract_docx_pages(content)
    if ext in _TEXT_EXTENSIONS:
        return _extract_text_pages(content)
    raise UnsupportedDocumentTypeError(
        f"Cannot ingest '.{ext}' files — supported types are: pdf, docx, "
        f"{', '.join(sorted(_TEXT_EXTENSIONS))}"
    )


def chunk_text(page: int, text: str) -> list[Chunk]:
    """Split one page into overlapping word-window chunks."""
    settings_ = get_settings()
    size = settings_.chunk_size
    overlap = settings_.chunk_overlap
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


def build_chunks(content: bytes, filename: str = "") -> list[Chunk]:
    """Extract and chunk an entire document. Raises `UnsupportedDocumentTypeError`
    if `filename`'s extension has no extractor."""
    chunks: list[Chunk] = []
    for page, text in extract_pages(content, filename):
        chunks.extend(chunk_text(page, text))
    return chunks


def embed_chunks(chunks: list[Chunk], bedrock: BedrockClient) -> list[list[float]]:
    """Embed every chunk; one Titan call per chunk (batch later if needed)."""
    return [bedrock.invoke_embedding(c.text) for c in chunks]
