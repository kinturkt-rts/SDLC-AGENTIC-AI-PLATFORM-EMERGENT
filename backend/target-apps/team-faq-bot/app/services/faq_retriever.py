"""FAQ chunk retrieval via pgvector cosine similarity.

Adapted for the faq_chunks table (serial PK, text embedding stored as vector(1024) on Postgres).
In SQLite tests, retrieval is mocked.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.bedrock_client import BedrockClient


@dataclass
class FaqMatch:
    """A single matched FAQ chunk."""
    chunk_id: int
    heading: str | None
    chunk_text: str
    score: float


class FaqRetriever(Protocol):
    def search(self, *, question: str, top_k: int) -> list[FaqMatch]: ...


@dataclass
class PgVectorFaqRetriever:
    """Cosine-similarity search over faq_chunks.embedding."""

    db: Session
    bedrock: BedrockClient

    def search(self, *, question: str, top_k: int = 5) -> list[FaqMatch]:
        query_vec = self.bedrock.invoke_embedding(question)
        vec_literal = "[" + ",".join(str(float(x)) for x in query_vec) + "]"

        sql = text(
            """
            SELECT c.id,
                   c.heading,
                   c.chunk_text,
                   1 - (c.embedding <=> CAST(:qvec AS vector)) AS score
            FROM faq_chunks c
            JOIN faq_collection fc ON fc.id = c.collection_id
            WHERE fc.is_active = true
            ORDER BY c.embedding <=> CAST(:qvec AS vector)
            LIMIT :k
            """
        )
        rows = self.db.execute(sql, {"qvec": vec_literal, "k": top_k}).mappings()
        return [
            FaqMatch(
                chunk_id=int(r["id"]),
                heading=r["heading"],
                chunk_text=r["chunk_text"],
                score=float(r["score"]),
            )
            for r in rows
        ]
