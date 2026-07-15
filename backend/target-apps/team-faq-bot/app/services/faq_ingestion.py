"""FAQ file ingestion — parse, chunk, embed, store.

Plain-text FAQ files are parsed into Q/A sections by heading patterns.
Each chunk is embedded via Bedrock Titan and stored in faq_chunks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import get_settings
from app.services.bedrock_client import BedrockClient


@dataclass(frozen=True)
class FaqSection:
    """A single FAQ section (heading + body text)."""
    heading: str | None
    text: str


def parse_faq_text(raw_text: str) -> list[FaqSection]:
    """Parse raw FAQ text into sections by Q: / ## headings."""
    # Try to split by Q: lines
    # Pattern: lines starting with Q: or ##
    lines = raw_text.splitlines()
    sections: list[FaqSection] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    heading_re = re.compile(r"^(Q:|##\s*|###\s*)(.*)$", re.IGNORECASE)

    for line in lines:
        m = heading_re.match(line.strip())
        if m:
            # Save previous section
            body = "\n".join(current_lines).strip()
            if body or current_heading:
                sections.append(FaqSection(heading=current_heading, text=body if body else line.strip()))
            current_heading = m.group(2).strip() or line.strip()
            current_lines = [line.strip()]
        else:
            current_lines.append(line)

    # Final section
    body = "\n".join(current_lines).strip()
    if body:
        sections.append(FaqSection(heading=current_heading, text=body))

    # If no headings were detected, chunk the whole text
    if not sections:
        sections = [FaqSection(heading=None, text=raw_text.strip())]

    return sections


def chunk_sections(sections: list[FaqSection]) -> list[FaqSection]:
    """Further chunk large sections by word window."""
    settings = get_settings()
    size = settings.chunk_size
    overlap = settings.chunk_overlap
    result: list[FaqSection] = []

    for section in sections:
        words = section.text.split()
        if len(words) <= size:
            result.append(section)
        else:
            step = max(size - overlap, 1)
            start = 0
            while start < len(words):
                window = words[start : start + size]
                result.append(FaqSection(heading=section.heading, text=" ".join(window)))
                start += step

    return result


def embed_sections(sections: list[FaqSection], bedrock: BedrockClient) -> list[list[float]]:
    """Embed each section text."""
    return [bedrock.invoke_embedding(s.text) for s in sections]
