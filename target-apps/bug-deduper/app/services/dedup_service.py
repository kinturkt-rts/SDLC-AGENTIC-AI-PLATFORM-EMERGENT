"""Semantic duplicate detection over open bugs using pgvector."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.bedrock_client import BedrockClient


@dataclass
class SimilarBug:
    id: str
    title: str
    description: str
    score: float


class DedupService:
    def __init__(self, bedrock: BedrockClient | None = None) -> None:
        self._bedrock = bedrock or BedrockClient()

    def embed_description(self, description: str) -> list[float]:
        return self._bedrock.invoke_embedding(description)

    def store_embedding(self, db: Session, bug_id: str, embedding: list[float]) -> None:
        vec_literal = "[" + ",".join(str(float(x)) for x in embedding) + "]"
        db.execute(
            text(
                """
                UPDATE bugs
                SET description_embedding = CAST(:vec AS vector),
                    updated_at = now()
                WHERE id = CAST(:bug_id AS uuid)
                """
            ),
            {"vec": vec_literal, "bug_id": bug_id},
        )
        db.commit()

    def find_similar(
        self,
        db: Session,
        *,
        embedding: list[float],
        exclude_bug_id: str | None = None,
        top_k: int | None = None,
    ) -> list[SimilarBug]:
        settings = get_settings()
        k = top_k or settings.dedup_top_k
        vec_literal = "[" + ",".join(str(float(x)) for x in embedding) + "]"

        sql = """
            SELECT id::text AS id,
                   title,
                   description,
                   1 - (description_embedding <=> CAST(:vec AS vector)) AS score
            FROM bugs
            WHERE status = 'open'
              AND description_embedding IS NOT NULL
        """
        params: dict[str, object] = {"vec": vec_literal, "k": k}
        if exclude_bug_id:
            sql += " AND id != CAST(:exclude_id AS uuid)"
            params["exclude_id"] = exclude_bug_id
        sql += """
            ORDER BY description_embedding <=> CAST(:vec AS vector)
            LIMIT :k
        """
        rows = db.execute(text(sql), params).mappings()
        return [
            SimilarBug(
                id=str(row["id"]),
                title=row["title"],
                description=row["description"],
                score=float(row["score"]),
            )
            for row in rows
        ]


def get_dedup_service() -> DedupService:
    return DedupService()
