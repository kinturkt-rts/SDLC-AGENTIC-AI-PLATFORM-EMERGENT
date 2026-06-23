from typing import List, Dict


RAG_SYSTEM_PROMPT = """
You are a helpful policy assistant. Your job is to answer questions about company policies based on the provided document excerpts.

Rules:
1. Only answer questions using information from the provided document excerpts
2. If the excerpts don't contain enough information to answer the question, say "I don't have enough information to answer that question based on the available documents."
3. Always cite the document title and page number when available
4. Be concise but comprehensive in your answers
5. If there are conflicting policies, mention both and suggest consulting with HR or IT
6. Use a professional but friendly tone

Format your response as:
- Direct answer to the question
- Supporting details from the documents
- Citations in format: (Document Title, Page X)
"""


def build_rag_prompt(question: str, retrieved_chunks: List[Dict]) -> str:
    """Build RAG prompt with question and retrieved document chunks"""
    
    context_parts = []
    for i, chunk in enumerate(retrieved_chunks, 1):
        doc_title = chunk.get('document_title', 'Unknown Document')
        page_num = chunk.get('page_number', 'Unknown')
        content = chunk.get('content', '')
        
        context_parts.append(
            f"Excerpt {i}:\n"
            f"Document: {doc_title}\n"
            f"Page: {page_num}\n"
            f"Content: {content}\n"
        )
    
    context = "\n---\n".join(context_parts)
    
    prompt = f"""{RAG_SYSTEM_PROMPT}

Document Excerpts:
{context}

---

Question: {question}

Answer:"""
    
    return prompt


def extract_confidence_score(response_text: str) -> float:
    """Extract confidence score from LLM response (simple heuristic)"""
    # Simple confidence scoring based on response characteristics
    if "I don't have enough information" in response_text:
        return 0.1
    elif "I'm not sure" in response_text or "uncertain" in response_text.lower():
        return 0.3
    elif "might" in response_text.lower() or "possibly" in response_text.lower():
        return 0.5
    elif "based on the documents" in response_text.lower():
        return 0.8
    else:
        return 0.7  # Default confidence
