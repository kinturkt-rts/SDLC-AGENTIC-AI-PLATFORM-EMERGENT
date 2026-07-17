"""POST /api/v1/ask — ask a question against the active FAQ collection."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.dependencies import DbSession, require_api_key
from app.models.question_log import QuestionLog
from app.services.bedrock_client import get_bedrock_client
from app.services.faq_retriever import FaqMatch, PgVectorFaqRetriever
from app.services.pii_sanitiser import sanitise
from app.services.prompts import FAQ_SYSTEM_PROMPT
from schemas.ask import AskRequest, AskResponse

logger = logging.getLogger(__name__)

router = APIRouter()

NOT_IN_FAQ_ANSWER = "This question is not covered in the FAQ."


def _build_context(matches: list[FaqMatch]) -> str:
    """Concatenate matched chunks into a prompt context string."""
    parts: list[str] = []
    for m in matches:
        heading = m.heading or "General"
        parts.append(f"[{heading}]\n{m.chunk_text}")
    return "\n\n".join(parts)


@router.post("/ask", response_model=AskResponse)
def ask_question(
    body: AskRequest,
    db: DbSession,
    _key: str = Depends(require_api_key),
) -> AskResponse:
    """Answer a user question from the active FAQ collection."""
    settings = get_settings()

    # Retrieve relevant chunks
    bedrock = get_bedrock_client()
    retriever = PgVectorFaqRetriever(db=db, bedrock=bedrock)
    matches = retriever.search(question=body.question, top_k=settings.retrieval_top_k)

    # Check confidence threshold
    relevant = [m for m in matches if m.score >= settings.confidence_threshold]

    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=settings.retention_days)

    if not relevant:
        # Log as not_in_faq
        log_entry = QuestionLog(
            question_text=sanitise(body.question),
            status="not_in_faq",
            logged_at=now,
            expires_at=expires,
        )
        db.add(log_entry)
        db.commit()
        return AskResponse(answer=NOT_IN_FAQ_ANSWER, citation=None)

    # Build context and invoke Bedrock
    context = _build_context(relevant)
    system_msg = FAQ_SYSTEM_PROMPT.format(context=context)

    llm_response = bedrock.invoke_text(
        user_message=body.question,
        system_message=system_msg,
    )

    # Check if LLM returned "not in FAQ" despite having context
    if "not in faq" in llm_response.lower():
        log_entry = QuestionLog(
            question_text=sanitise(body.question),
            status="not_in_faq",
            logged_at=now,
            expires_at=expires,
        )
        db.add(log_entry)
        db.commit()
        return AskResponse(answer=NOT_IN_FAQ_ANSWER, citation=None)

    # Determine citation from best match heading
    citation = relevant[0].heading or "FAQ"

    # Log as answered
    log_entry = QuestionLog(
        question_text=sanitise(body.question),
        status="answered",
        logged_at=now,
        expires_at=expires,
    )
    db.add(log_entry)
    db.commit()

    return AskResponse(answer=llm_response.strip(), citation=citation)
