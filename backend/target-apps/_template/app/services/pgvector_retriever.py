"""pgvector similarity retrieval for the local RAG pattern.

Reads from the `document_chunks` table created by database-agent. Adjust the
table/column names and schema to match db/HANDOFF.md. Cosine distance (`<=>`)
is used; similarity = 1 - distance.

Routers depend on `Retriever` (the Protocol) so tests can inject a fake without
a live database or Bedrock.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.bedrock_client import BedrockClient


@dataclass
class RetrievedChunk:
    doc_id: str
    title: str
    page: int
    snippet: str
    score: float


class Retriever(Protocol):
    def search(
        self, *, question: str, collection_ids: Iterable[str], top_k: int = 5
    ) -> list[RetrievedChunk]: ...


@dataclass
class PgVectorRetriever:
    """Cosine-similarity search over `document_chunks.embedding`."""

    db: Session
    bedrock: BedrockClient

    def search(
        self, *, question: str, collection_ids: Iterable[str], top_k: int = 5
    ) -> list[RetrievedChunk]:
        ids = list(collection_ids)
        if not ids:
            return []
        query_vec = self.bedrock.invoke_embedding(question)
        # pgvector expects the literal '[v1,v2,...]' form for the vector param.
        vec_literal = "[" + ",".join(str(float(x)) for x in query_vec) + "]"

        sql = text(
            """
            SELECT c.doc_id,
                   d.title,
                   c.page,
                   c.text AS snippet,
                   1 - (c.embedding <=> CAST(:qvec AS vector)) AS score
            FROM document_chunks c
            JOIN documents d ON d.id = c.doc_id
            WHERE d.collection_id = ANY(:cids)
            ORDER BY c.embedding <=> CAST(:qvec AS vector)
            LIMIT :k
            """
        )
        rows = self.db.execute(
            sql, {"qvec": vec_literal, "cids": ids, "k": top_k}
        ).mappings()
        return [
            RetrievedChunk(
                doc_id=str(r["doc_id"]),
                title=r["title"],
                page=int(r["page"]),
                snippet=r["snippet"],
                score=float(r["score"]),
            )
            for r in rows
        ]
