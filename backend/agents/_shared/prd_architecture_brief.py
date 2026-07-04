"""Deterministic PRD → short architecture brief for architect diagram generation."""

from __future__ import annotations

import re
from typing import Iterable

_DEFAULT_MAX_CHARS = 1500

# Section headings to include (matched against normalized ## title text).
_BRIEF_SECTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"overview", re.I), "Overview"),
    (re.compile(r"non-?goals|out of scope", re.I), "Out of scope"),
    (re.compile(r"data\s*&?\s*integrations?", re.I), "Data & integrations"),
    (re.compile(r"^stack$|technical\s+stack|architecture", re.I), "Stack / architecture"),
    (re.compile(r"delivery|ui\s*/?\s*client", re.I), "Delivery / UI"),
)


def _prd_title(prd_text: str) -> str:
    for line in prd_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def _split_markdown_sections(prd_text: str) -> list[tuple[str, str]]:
    """Return (heading, body) pairs for each ## section in the PRD."""
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []

    for line in prd_text.splitlines():
        if line.startswith("## "):
            if current_heading or current_lines:
                sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = line[3:].strip()
            current_lines = []
        elif current_heading:
            current_lines.append(line)

    if current_heading or current_lines:
        sections.append((current_heading, "\n".join(current_lines).strip()))
    return sections


def _normalize_heading(heading: str) -> str:
    return re.sub(r"^\d+\.\s*", "", heading.strip())


def _select_section_bodies(sections: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    selected: list[tuple[str, str]] = []
    seen_labels: set[str] = set()
    for heading, body in sections:
        if not body.strip():
            continue
        norm = _normalize_heading(heading)
        for pattern, label in _BRIEF_SECTION_PATTERNS:
            if pattern.search(norm) and label not in seen_labels:
                selected.append((label, body.strip()))
                seen_labels.add(label)
                break
    return selected


def extract_architecture_brief_from_prd(prd_text: str, *, max_chars: int = _DEFAULT_MAX_CHARS) -> str:
    """Build a compact architecture brief from PRD markdown (deterministic, no LLM)."""
    text = prd_text.strip()
    if not text:
        return ""

    parts: list[str] = []
    title = _prd_title(text)
    if title:
        parts.append(f"Feature: {title}")

    for label, body in _select_section_bodies(_split_markdown_sections(text)):
        parts.append(f"### {label}\n{body}")

    brief = "\n\n".join(parts).strip()
    if len(brief) <= max_chars:
        return brief
    return brief[: max_chars - 3].rstrip() + "..."
