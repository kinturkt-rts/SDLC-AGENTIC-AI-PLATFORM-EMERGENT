"""ChromaDB-based vector store for runbook step search.

Fallback: if chromadb/sentence-transformers not installed, all functions
are no-ops so the API still works for CRUD without vector search.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings

logger = logging.getLogger(__name__)

_collection = None
_embed_fn = None


def _get_collection():
    """Lazy-init ChromaDB collection."""
    global _collection, _embed_fn
    if _collection is not None:
        return _collection
    try:
        import chromadb
        from chromadb.utils import embedding_functions

        settings = get_settings()
        client = chromadb.Client()  # in-memory for MVP
        _embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model,
        )
        _collection = client.get_or_create_collection(
            name="runbook_steps",
            embedding_function=_embed_fn,
        )
        return _collection
    except ImportError:
        logger.warning("chromadb or sentence-transformers not installed; vector search disabled")
        return None
    except Exception as e:
        logger.warning("Vector store init failed: %s", e)
        return None


def upsert_step(step, runbook_id: str, service_id: str) -> None:
    """Upsert a single step into the vector index."""
    col = _get_collection()
    if col is None:
        return
    col.upsert(
        ids=[str(step.id)],
        documents=[step.body_text],
        metadatas=[{
            "runbook_id": str(runbook_id),
            "service_id": str(service_id),
            "step_number": step.step_number,
            "title": step.title,
        }],
    )


def index_runbook_steps(db: Session, runbook_id: str) -> int:
    """Index all steps for a runbook."""
    from app.models.runbook import Runbook
    from app.models.runbook_step import RunbookStep

    col = _get_collection()
    if col is None:
        return 0
    rb = db.get(Runbook, runbook_id)
    if not rb:
        return 0
    steps = db.scalars(
        select(RunbookStep).where(RunbookStep.runbook_id == runbook_id)
    ).all()
    for step in steps:
        upsert_step(step, runbook_id, rb.service_id)
    return len(steps)


def remove_runbook_steps(runbook_id: str) -> None:
    """Remove all steps for a runbook from the vector index."""
    col = _get_collection()
    if col is None:
        return
    try:
        results = col.get(where={"runbook_id": str(runbook_id)})
        if results and results["ids"]:
            col.delete(ids=results["ids"])
    except Exception as e:
        logger.warning("remove_runbook_steps failed: %s", e)


def refresh_full_index(db: Session) -> int:
    """Re-index all active runbook steps."""
    from app.models.runbook import Runbook
    from app.models.runbook_step import RunbookStep

    col = _get_collection()
    if col is None:
        return 0

    # Clear existing
    try:
        existing = col.get()
        if existing and existing["ids"]:
            col.delete(ids=existing["ids"])
    except Exception:
        pass

    # Re-index active steps
    active_runbooks = db.scalars(
        select(Runbook).where(Runbook.lifecycle_status == "active")
    ).all()
    count = 0
    for rb in active_runbooks:
        steps = db.scalars(
            select(RunbookStep).where(RunbookStep.runbook_id == rb.id)
        ).all()
        for step in steps:
            upsert_step(step, rb.id, rb.service_id)
            count += 1
    return count


def query_steps(
    query: str,
    service_id: str | None = None,
    top_k: int = 15,
) -> list[dict[str, Any]]:
    """Query the vector store. Returns list of dicts with metadata + score."""
    col = _get_collection()
    if col is None:
        return []

    where_filter = None
    if service_id:
        where_filter = {"service_id": str(service_id)}

    try:
        results = col.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filter,
        )
    except Exception as e:
        logger.warning("Vector query failed: %s", e)
        return []

    items: list[dict[str, Any]] = []
    if not results or not results.get("ids") or not results["ids"][0]:
        return items

    ids = results["ids"][0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    # Need to look up service_name and runbook_title from DB
    # Import here to avoid circular
    from app.models.runbook import Runbook
    from app.models.service import Service
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        for i, step_id in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            distance = distances[i] if i < len(distances) else 1.0
            score = max(0.0, 1.0 - distance)  # Convert distance to similarity

            rb_id = meta.get("runbook_id", "")
            svc_id = meta.get("service_id", "")

            # Fetch names
            rb = db.get(Runbook, rb_id)
            svc = db.get(Service, svc_id)

            doc = documents[i] if i < len(documents) else ""
            excerpt = doc[:200] if doc else ""

            items.append({
                "step_id": step_id,
                "runbook_id": rb_id,
                "service_id": svc_id,
                "service_name": svc.name if svc else "",
                "runbook_title": rb.title if rb else "",
                "step_number": meta.get("step_number", 0),
                "step_title": meta.get("title", ""),
                "excerpt": excerpt,
                "score": score,
            })
    finally:
        db.close()

    return items
