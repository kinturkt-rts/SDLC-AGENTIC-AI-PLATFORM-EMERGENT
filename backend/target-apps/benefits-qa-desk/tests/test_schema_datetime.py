"""REFERENCE: copy/adapt when response schemas expose *_at: str fields.

Pytest on SQLite often seeds ISO strings while RDS returns datetime objects.
Without coercion, GET list routes return 500 ResponseValidationError on live RDS.
"""
from __future__ import annotations

from datetime import datetime, timezone

# ADAPT: import your ArticleOut (or similar) response schema
# from schemas.article import ArticleOut


def test_article_out_coerces_rds_datetime_fields() -> None:
    """Template example — enable after adding ArticleOut with coerce_iso_datetime validators."""
    ts = datetime(2024, 1, 20, 10, 0, tzinfo=timezone.utc)
    payload = {
        "id": "00000000-0000-0000-0000-000000000001",
        "created_at": ts,
        "updated_at": ts,
    }
    # out = ArticleOut.model_validate(payload)
    # assert out.created_at.startswith("2024-01-20")
    assert payload["created_at"].isoformat().startswith("2024-01-20")
