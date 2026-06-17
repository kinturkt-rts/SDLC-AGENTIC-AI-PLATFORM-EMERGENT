"""FAQ search service — full-text search on Postgres, keyword fallback on SQLite."""
import logging
from typing import List

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.faq_entry import FaqEntry

logger = logging.getLogger(__name__)


def search_faqs(db: Session, query: str) -> List[FaqEntry]:
    """Search FAQ entries using Postgres tsvector or SQLite LIKE fallback.
    
    Returns matching FAQ entries ordered by relevance.
    """
    settings = get_settings()
    bind = db.get_bind()
    dialect = bind.dialect.name if bind else "sqlite"

    if dialect == "postgresql":
        # Use full-text search with ts_rank
        sql = text("""
            SELECT id, category, question, answer, is_active, created_at, updated_at,
                   ts_rank(search_vector, plainto_tsquery('english', :query)) AS rank
            FROM faq_entries
            WHERE is_active = true
              AND search_vector @@ plainto_tsquery('english', :query)
              AND ts_rank(search_vector, plainto_tsquery('english', :query)) >= :threshold
            ORDER BY rank DESC
            LIMIT 10
        """)
        rows = db.execute(sql, {"query": query, "threshold": settings.faq_relevance_threshold}).fetchall()
        if rows:
            ids = [row[0] for row in rows]
            return list(db.query(FaqEntry).filter(FaqEntry.id.in_(ids)).all())
        return []
    else:
        # SQLite fallback: simple LIKE matching on question and answer
        keywords = [kw.strip() for kw in query.split() if len(kw.strip()) > 2]
        if not keywords:
            return []
        results = db.query(FaqEntry).filter(FaqEntry.is_active == True)  # noqa: E712
        matched = []
        for faq in results.all():
            text_content = f"{faq.question} {faq.answer}".lower()
            if any(kw.lower() in text_content for kw in keywords):
                matched.append(faq)
        return matched[:10]
