"""Regression: RDS TIMESTAMPTZ must serialize through ArticleOut."""
from __future__ import annotations

from datetime import datetime, timezone

from schemas.article import ArticleOut


def test_article_out_coerces_rds_datetime_fields() -> None:
    ts = datetime(2024, 1, 20, 10, 0, tzinfo=timezone.utc)
    out = ArticleOut.model_validate(
        {
            "id": "c3000000-0000-0000-0000-000000000001",
            "title": "VPN",
            "body": "body",
            "category_id": "b2000000-0000-0000-0000-000000000001",
            "tags": [],
            "author_id": "a1000000-0000-0000-0000-000000000001",
            "status": "published",
            "created_at": ts,
            "updated_at": ts,
            "published_at": ts,
            "archived_at": None,
        }
    )
    assert out.created_at.startswith("2024-01-20")
    assert out.published_at is not None
