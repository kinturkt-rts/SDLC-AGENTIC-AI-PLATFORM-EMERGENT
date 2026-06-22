"""Similarity computation service.

MVP uses simple text overlap (Jaccard-like) as a fallback.
In production, this would use embeddings + cosine similarity via pgvector.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.article import Article
from schemas.article import SimilarArticleItem


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """Compute simple word-level Jaccard similarity."""
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0


def compute_similar_articles(
    db: Session,
    article: Any,
    threshold: float = 0.75,
    max_results: int = 5,
) -> list[SimilarArticleItem]:
    """Find similar published articles by body content.

    Uses Jaccard word overlap as MVP fallback.
    In production, would use pgvector cosine similarity on embeddings.
    """
    published = (
        db.query(Article)
        .filter(Article.status == "published", Article.id != str(article.id))
        .all()
    )

    scored: list[SimilarArticleItem] = []
    for pub in published:
        score = _jaccard_similarity(article.body or "", pub.body or "")
        if score >= threshold:
            excerpt = (pub.body or "")[:200]
            scored.append(SimilarArticleItem(
                id=str(pub.id),
                title=pub.title,
                excerpt=excerpt,
                score=round(score, 3),
            ))

    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:max_results]
