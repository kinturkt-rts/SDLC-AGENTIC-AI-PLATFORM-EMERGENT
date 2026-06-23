from typing import List
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from app.dependencies import DbSession, CurrentUser, get_user_collection_access
from app.models.chat import ChatSession, ChatMessage
from app.models.collection import Collection
from app.models.pg_types import CollectionMemberRole
from app.services.audit import log_audit_event
from app.services.pgvector_retriever import retrieve_relevant_chunks
from app.services.bedrock_client import invoke_text
from app.services.prompts import build_rag_prompt, extract_confidence_score
from app.config import get_settings
from schemas.chat import ChatRequest, ChatResponse, ChatMessage as ChatMessageSchema, Citation

router = APIRouter()


@router.post("/{collection_id}/chat", response_model=ChatResponse)
def chat_with_collection(
    collection_id: int,
    body: ChatRequest,
    request: Request,
    current_user: CurrentUser,
    db: DbSession
):
    """Ask a question about documents in the collection"""
    settings = get_settings()
    
    # Check collection access
    get_user_collection_access(db, current_user, collection_id)
    
    # Get or create chat session
    if body.session_id:
        session = db.query(ChatSession).filter(
            ChatSession.id == body.session_id,
            ChatSession.collection_id == collection_id,
            ChatSession.user_id == current_user.id
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
    else:
        # Create new session
        session = ChatSession(
            collection_id=collection_id,
            user_id=current_user.id
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    
    # Store user message
    user_message = ChatMessage(
        session_id=session.id,
        content=body.message,
        is_user=True
    )
    db.add(user_message)
    
    try:
        # Retrieve relevant document chunks
        retrieved_chunks = retrieve_relevant_chunks(
            db=db,
            collection_id=collection_id,
            query=body.message,
            top_k=settings.retrieval_top_k
        )
        
        if not retrieved_chunks:
            # No relevant documents found
            answer = "I don't have any relevant documents to answer your question. Please make sure documents have been uploaded and processed successfully."
            confidence = 0.0
            citations = []
            refused = True
        else:
            # Generate answer using RAG
            rag_prompt = build_rag_prompt(body.message, retrieved_chunks)
            
            try:
                answer = invoke_text(rag_prompt)
                confidence = extract_confidence_score(answer)
                
                # Check confidence threshold
                if confidence < settings.confidence_threshold:
                    answer = "I don't have enough information to provide a confident answer to your question based on the available documents. Please try rephrasing your question or consult the documents directly."
                    refused = True
                else:
                    refused = False
                
                # Build citations
                citations = [
                    Citation(
                        document_title=chunk['document_title'],
                        page_number=chunk['page_number'],
                        confidence=chunk['confidence'],
                        content_preview=chunk['content'][:200] + "..." if len(chunk['content']) > 200 else chunk['content']
                    )
                    for chunk in retrieved_chunks
                ]
                
            except Exception as e:
                print(f"LLM generation failed: {e}")
                answer = "I'm experiencing technical difficulties generating an answer. Please try again later."
                confidence = 0.0
                citations = []
                refused = True
    
    except Exception as e:
        print(f"RAG pipeline failed: {e}")
        answer = "I'm experiencing technical difficulties processing your question. Please try again later."
        confidence = 0.0
        citations = []
        refused = True
    
    # Store assistant message
    assistant_message = ChatMessage(
        session_id=session.id,
        content=answer,
        is_user=False,
        confidence_score=confidence,
        citations=[citation.dict() for citation in citations] if citations else None
    )
    db.add(assistant_message)
    db.commit()
    
    # Log chat interaction
    log_audit_event(
        db=db,
        user_id=current_user.id,
        action="chat_query",
        resource_type="collection",
        resource_id=collection_id,
        details={
            "question": body.message,
            "confidence": confidence,
            "refused": refused,
            "session_id": session.id
        },
        ip_address=request.client.host if request.client else None
    )
    
    return ChatResponse(
        answer=answer,
        confidence=confidence,
        citations=citations,
        session_id=session.id,
        refused=refused
    )


@router.get("/{collection_id}/chat/{session_id}", response_model=List[ChatMessageSchema])
def get_chat_history(
    collection_id: int,
    session_id: int,
    current_user: CurrentUser,
    db: DbSession
):
    """Get chat history for a session"""
    # Check collection access
    get_user_collection_access(db, current_user, collection_id)
    
    # Get session
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.collection_id == collection_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    # Get messages
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at).all()
    
    return messages
