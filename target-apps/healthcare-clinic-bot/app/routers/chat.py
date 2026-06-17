"""Chat router — sessions and messaging."""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.services.bedrock_client import get_bedrock_client
from app.services.faq_search import search_faqs
from app.services.prompts import SYSTEM_PROMPT
from app.services.sensitive_guard import REDIRECT_MESSAGE, contains_sensitive_data
from schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    MessageOut,
)

logger = logging.getLogger(__name__)

router = APIRouter()

DISCLAIMER = (
    "This information is for general purposes only and is not medical advice. "
    "For emergencies, call 911. For personal medical questions, please contact the clinic directly."
)

FALLBACK_MESSAGE = (
    "I don't have information on that topic. For further assistance, "
    "please contact the clinic directly at (555) 123-4567."
)


@router.post("/sessions", response_model=CreateSessionResponse, status_code=201)
def create_session(body: CreateSessionRequest, db: Session = Depends(get_db)):
    """Create a new chat session."""
    session = ChatSession(session_label=body.session_label)
    db.add(session)
    db.commit()
    db.refresh(session)
    return CreateSessionResponse(session_id=str(session.id), created_at=session.created_at)


@router.post("/message", response_model=ChatMessageResponse)
def send_message(body: ChatMessageRequest, db: Session = Depends(get_db)):
    """Process a chat message — sensitive guard → FAQ search → Bedrock or fallback."""
    # Validate session exists
    session = db.query(ChatSession).filter(ChatSession.id == body.session_id).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Sensitive data guard (FR-4) — do NOT persist the message
    if contains_sensitive_data(body.message):
        # Store only a sanitized note, not the actual sensitive content
        reply_text = REDIRECT_MESSAGE
        # Save assistant reply only
        assistant_msg = ChatMessage(
            session_id=body.session_id,
            role="assistant",
            content=reply_text,
            is_fallback=False,
        )
        db.add(assistant_msg)
        db.commit()
        return ChatMessageResponse(
            session_id=body.session_id,
            reply=reply_text,
            disclaimer=DISCLAIMER,
            is_fallback=False,
        )

    # Persist user message
    user_msg = ChatMessage(
        session_id=body.session_id,
        role="user",
        content=body.message,
        is_fallback=False,
    )
    db.add(user_msg)
    db.flush()

    # FAQ search
    faq_results = search_faqs(db, body.message)

    if not faq_results:
        # Fallback — no relevant FAQ found
        reply_text = FALLBACK_MESSAGE
        is_fallback = True
    else:
        # Grounded answer via Bedrock
        faq_context = "\n\n".join(
            f"Q: {faq.question}\nA: {faq.answer}" for faq in faq_results
        )
        system = SYSTEM_PROMPT.format(faq_context=faq_context)
        start = time.time()
        try:
            bedrock = get_bedrock_client()
            reply_text = bedrock.invoke_text(system, body.message)
        except Exception as exc:
            logger.error("Bedrock call failed: %s", exc, extra={"session_id": body.session_id})
            # Graceful degradation: return FAQ answer directly
            reply_text = faq_results[0].answer
        elapsed = time.time() - start
        logger.info(
            "Bedrock call completed",
            extra={"session_id": body.session_id, "faq_count": len(faq_results), "latency_ms": int(elapsed * 1000)},
        )
        is_fallback = False

    # Persist assistant reply
    assistant_msg = ChatMessage(
        session_id=body.session_id,
        role="assistant",
        content=reply_text,
        is_fallback=is_fallback,
    )
    db.add(assistant_msg)
    db.commit()

    return ChatMessageResponse(
        session_id=body.session_id,
        reply=reply_text,
        disclaimer=DISCLAIMER,
        is_fallback=is_fallback,
    )


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def get_session_messages(session_id: str, db: Session = Depends(get_db)):
    """Retrieve all messages in a chat session, ordered by creation time."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
        .all()
    )
    return messages
