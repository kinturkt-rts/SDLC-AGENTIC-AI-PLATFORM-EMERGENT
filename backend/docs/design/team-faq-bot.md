# Team FAQ Bot — Solution Design

## 1. Summary
Single-team FAQ chatbot: admins upload a plain-text FAQ file; users ask natural-language questions via REST or Streamlit chat UI; FastAPI retrieves top-k chunks via pgvector cosine similarity, then Bedrock Claude composes a cited answer (or returns "not in FAQ"). Primary DB: RDS Postgres + pgvector. Auth: shared `X-API-Key` header. `Diagram: /tmp/generated-diagrams/team-faq-bot.png`. TBD: Bedrock model selection (Haiku vs Sonnet), final retention policy sign-off.

## 2. Stack
| Layer | Technology | Path / Notes |
|-------|------------|--------------|
| API | FastAPI | `target-apps/team-faq-bot/app/` |
| UI | Streamlit | `ui/streamlit_app.py` — calls FastAPI over HTTP (port 8501) |
| DB | RDS Postgres + pgvector | `faq_chunks`, `question_log` tables |
| Embeddings | Bedrock Titan Embed (`amazon.titan-embed-text-v2:0`) | 1024-dim vectors |
| LLM | Bedrock Claude (`anthropic.claude-3-haiku`) | Server-side only, IAM role |
| Storage | Local filesystem | `data/faq/<team>.txt` — no S3 |

## 3. Data model
| Table | Columns | Indexes / Constraints |
|-------|---------|----------------------|
| `faq_collection` | `id serial PK`, `filename text NOT NULL`, `raw_text text NOT NULL`, `char_count int NOT NULL`, `uploaded_at timestamptz DEFAULT now()`, `is_active bool DEFAULT true` | `idx_faq_active (is_active)`; only one `is_active=true` enforced in app |
| `faq_chunks` | `id serial PK`, `collection_id int FK(faq_collection.id)`, `heading text`, `chunk_text text NOT NULL`, `embedding vector(1024) NOT NULL` | `idx_chunks_embedding` ivfflat (vector_cosine_ops); `idx_chunks_collection (collection_id)` |
| `question_log` | `id serial PK`, `question_text text NOT NULL`, `status text NOT NULL CHECK(status IN ('answered','not_in_faq'))`, `logged_at timestamptz DEFAULT now()`, `expires_at timestamptz NOT NULL` | `idx_qlog_status_logged (status, logged_at)`; `idx_qlog_expires (expires_at)` |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| `POST` | `/api/v1/ask` | `{"question": str}` | `{"answer": str, "citation": str\|null}` | FR-3/4/5; key auth; logs to `question_log` |
| `POST` | `/api/v1/upload` | `multipart/form-data: file` (.txt) | `{"message": str, "char_count": int}` | FR-1/2; admin key required; replaces active collection |
| `GET` | `/api/v1/gaps` | `?from=YYYY-MM-DD&to=YYYY-MM-DD` | `[{"id":int,"question_text":str,"logged_at":str}]` | FR-9; admin key; filters `status='not_in_faq'` |
| `GET` | `/api/v1/health` | — | `{"status":"ok"}` | liveness check |

## 5. Rules
- **API Key Auth (NFR-5)**: `X-API-Key` header validated in FastAPI middleware against `API_KEY` env var; missing/wrong key → 401. Admin-only endpoints (`/upload`, `/gaps`) require `ADMIN_API_KEY` env var; Streamlit: stores key in `st.session_state.api_key`; admin panel visible only when `st.session_state.is_admin=True`.
- **File validation (FR-1, FR-2)**: `POST /upload` rejects files > 50,000 chars → HTTP 400 with size-limit message; also rejects empty files or files with no recognisable Q/A content; existing collection unchanged on rejection.
- **"Not in FAQ" fallback (FR-4)**: cosine similarity < configurable threshold (default 0.75) → return `{"answer":"This question is not covered in the FAQ.","citation":null}` without invoking Bedrock LLM.
- **PII sanitisation (NFR-4, FR-8)**: before writing `question_log`, strip email/phone patterns via regex; log must not contain user identity or IP; enforced in `services/logging_service.py`.
- **Data retention (NFR-10)**: `expires_at = logged_at + 90 days` set on insert; APScheduler daily job `DELETE FROM question_log WHERE expires_at < now()`.
- **Single active collection (FR-10)**: on successful upload, `UPDATE faq_collection SET is_active=false WHERE is_active=true` then insert new record; atomic in one transaction.
- **Structured logging (NFR-8)**: JSON logs emitted for every request, Bedrock call, and upload event with `request_id`, `endpoint`, `duration_ms`, `outcome`; via `logging_service.py` middleware.
- **Prompt guard (FR-4, risk)**: Bedrock prompt instructs "Answer ONLY from provided FAQ text. If answer not present, respond: not in FAQ." Response parsed; if phrase detected → override with standard fallback, citation=null.

## 6. DB delivery
1. Migration order: `001_enable_pgvector.sql`, `002_faq_collection.sql`, `003_faq_chunks.sql`, `004_question_log.sql`
2. Seed data: one `faq_collection` row with `is_active=false` (placeholder); sample `question_log` rows with `status='not_in_faq'` for gap-list testing
3. Athena / NoSQL: not used
