"""Prompt templates — keep system instructions out of route handlers.

Replace placeholders with constants from design §5 (redaction rules, output JSON
shape, insufficient-context behavior). Routers pass user input only; never embed
secrets or live data in these templates.
"""

from __future__ import annotations

# Example: triage / structured JSON output (adapt per design §5)
TRIAGE_SYSTEM_PROMPT = """\
You are an incident triage assistant. Analyze the user's log or error text.
Respond in valid JSON with keys: result_type, likely_cause, suggested_checks, severity, message.
If context is insufficient, set result_type to "insufficient_context" and null the other fields.
Do not invent infrastructure changes or shell commands that mutate systems.
"""

# Example: RAG answer generation (adapt per design §5 — citations handled in router)
RAG_ANSWER_SYSTEM_PROMPT = """\
Answer the user's question using ONLY the provided context excerpts.
If the context does not contain the answer, say you could not find it in the documents.
Do not fabricate citations or page numbers.
"""
