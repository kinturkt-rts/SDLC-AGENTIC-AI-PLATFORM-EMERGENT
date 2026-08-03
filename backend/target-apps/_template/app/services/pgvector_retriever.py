"""pgvector similarity retrieval for the local RAG pattern.

Reads from the `document_chunks` table created by database-agent. Adjust the
table/column names, dataclass fields, and SQL below to match the REAL schema
in the database handoff doc (databaseHandoffPath) (they are illustrative placeholders here, not a fixed
contract) — e.g. `doc_id` → `document_id`, `text` → `content`,
`d.collection_id` → whatever join actually scopes access for this app.

This retriever MUST be wired into the query router via `get_retriever()`
(a FastAPI dependency, mirroring `get_bedrock_client()`) — never leave it
unused in favor of an unranked "grab the first N chunks" query. An unused
retriever means answers aren't actually grounded by relevance, and the
"insufficient information" fallback ends up meaning "zero chunks exist"
instead of "nothing relevant was found for this question."

Routers depend on `get_retriever` rather than instantiating `PgVectorRetriever`
directly, so tests can override it with a fake `Retriever` and never touch a
live Postgres/pgvector connection (the `<=>` operator and `vector` cast used
here have no SQLite equivalent — wiring raw pgvector SQL directly into a
router breaks the SQLite-based test suite).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.dependencies import DbSession
from app.services.bedrock_client import BedrockClient, get_bedrock_client


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


def get_retriever(
    db: DbSession,
    bedrock: BedrockClient = Depends(get_bedrock_client),
) -> Retriever:
    """FastAPI dependency factory; override in tests with a fake Retriever."""
    return PgVectorRetriever(db=db, bedrock=bedrock)
