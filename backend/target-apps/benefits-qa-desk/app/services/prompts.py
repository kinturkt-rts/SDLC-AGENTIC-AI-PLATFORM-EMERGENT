"""RAG prompt templates."""
from __future__ import annotations


def build_qa_prompt(question: str, context_chunks: list[tuple[str, str]]) -> str:
    """Build the RAG prompt for grounded Q&A.

    Args:
        question: User's plain-English question.
        context_chunks: List of (chunk_text, source_filename) tuples.

    Returns:
        Formatted prompt string for the LLM.
    """
    context_block = "\n\n".join(
        f"[Source: {fname}]\n{text}" for text, fname in context_chunks
    )
    prompt = (
        "You are a Benefits Q&A assistant. Answer the user's question ONLY using "
        "the provided document context below. If the context does not contain "
        "enough information to answer the question, respond with exactly: "
        "\"Not found in documents\"\n\n"
        "Do NOT invent, assume, or extrapolate information not present in the context.\n\n"
        "=== DOCUMENT CONTEXT ===\n"
        f"{context_block}\n\n"
        "=== USER QUESTION ===\n"
        f"{question}\n\n"
        "Answer:"
    )
    return prompt
