"""pgvector cosine-similarity search for bug deduplication.

On Postgres (production): uses <=> cosine distance operator.
On SQLite (test): returns empty list (no vector support).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def find_similar_bugs(
    db: Session,
    embedding: list[float],
    top_k: int = 3,
    exclude_id: str | None = None,
) -> list[dict[str, Any]]:
    """Search for similar open bugs using cosine similarity.

    Returns list of {id, title, similarity_score} sorted desc by score.
    """
    dialect = db.bind.dialect.name if db.bind else "sqlite"
    if dialect == "sqlite":
        return []

    # Postgres pgvector cosine distance: 1 - (a <=> b) = similarity
    embedding_str = "[" + ",".join(str(f) for f in embedding) + "]"

    exclude_clause = ""
    params: dict[str, Any] = {
        "embedding": embedding_str,
        "top_k": top_k,
    }
    if exclude_id:
        exclude_clause = "AND id != :exclude_id"
        params["exclude_id"] = exclude_id

    # CAST avoids :param::type — SQLAlchemy treats :: as bind-name syntax, not PG cast.
    query = text(f"""
        SELECT id, title, 1 - (embedding <=> CAST(:embedding AS vector)) AS similarity_score
        FROM bugs
        WHERE status = 'open'
          AND embedding IS NOT NULL
          {exclude_clause}
        ORDER BY embedding <=> CAST(:embedding AS vector) ASC
        LIMIT :top_k
    """)

    rows = db.execute(query, params).fetchall()
    return [
        {"id": str(row[0]), "title": row[1], "similarity_score": float(row[2])}
        for row in rows
    ]
