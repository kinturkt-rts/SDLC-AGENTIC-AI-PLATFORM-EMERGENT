"""Tests for deterministic PRD architecture brief extraction."""

from __future__ import annotations

from pathlib import Path

from _shared.prd_architecture_brief import extract_architecture_brief_from_prd

_SAMPLE = Path(__file__).resolve().parents[1] / "docs" / "PRD" / "contacts-api.md"


def test_extract_architecture_brief_includes_key_sections() -> None:
    prd = _SAMPLE.read_text(encoding="utf-8")
    brief = extract_architecture_brief_from_prd(prd)

    assert "Feature: Contact Directory API" in brief
    assert "### Overview" in brief
    assert "### Out of scope" in brief
    assert "JWT authentication" in brief
    assert "### Data & integrations" in brief
    assert "PostgreSQL" in brief


def test_extract_architecture_brief_respects_max_chars() -> None:
    prd = _SAMPLE.read_text(encoding="utf-8")
    brief = extract_architecture_brief_from_prd(prd, max_chars=200)

    assert len(brief) <= 200
    assert brief.endswith("...")


def test_extract_architecture_brief_empty_input() -> None:
    assert extract_architecture_brief_from_prd("") == ""
    assert extract_architecture_brief_from_prd("   \n") == ""
