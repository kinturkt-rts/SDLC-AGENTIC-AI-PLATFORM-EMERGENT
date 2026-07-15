"""Document ingestion — extract text and chunk."""
from __future__ import annotations

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


def extract_and_chunk(file_path: str, file_type: str) -> list[str]:
    """Extract text from a file and split into chunks."""
    text = _extract_text(file_path, file_type)
    if not text.strip():
        raise ValueError("No text could be extracted from the document.")
    return _chunk_text(text)


def _extract_text(file_path: str, file_type: str) -> str:
    """Extract plain text from supported file types."""
    if file_type == "text/plain":
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    elif file_type == "application/pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages)
        except Exception as exc:
            raise ValueError(f"PDF extraction failed: {exc}") from exc
    elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        try:
            import docx
            doc = docx.Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as exc:
            raise ValueError(f"DOCX extraction failed: {exc}") from exc
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks."""
    settings = get_settings()
    chunk_size = settings.chunk_size
    overlap = settings.chunk_overlap

    words = text.split()
    chunks: list[str] = []
    i = 0
    while i < len(words):
        chunk_words = words[i: i + chunk_size]
        chunks.append(" ".join(chunk_words))
        i += chunk_size - overlap
    return chunks if chunks else [text]
