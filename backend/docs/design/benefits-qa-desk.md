# Benefits Q&A Desk — Solution Design

## 1. Summary
Internal HR tool for uploading benefit PDFs into named collections and answering employee questions via RAG (pgvector + Bedrock). FastAPI backend enforces RBAC; Streamlit frontend communicates exclusively via HTTP. Auth: JWT Bearer (username/password, 8-hour TTL). TBD: Bedrock model tier confirmation (Open Q-1); collection-level access scoping (Open Q-5).
Diagram: `docs/generated-diagrams/benefits-qa-desk.png`

## 2. Stack
| Layer | Technology | Path / Notes |
|-------|------------|--------------|
| UI | Streamlit | `ui/streamlit_app.py` — calls FastAPI over HTTP (port 8501) |
| API | FastAPI | `target-apps/benefits-qa-desk/app/` — all RBAC, Bedrock calls, audit writes |
| Auth | PyJWT | Username/password → `/auth/token` → JWT; role in claims; 8-hour TTL via env |
| DB | Postgres + pgvector | App data + 1024-dim chunk embeddings; SQLAlchemy ORM + Alembic |
| AI | Amazon Bedrock (boto3) | Titan Embed `amazon.titan-embed-text-v2:0`; Claude (Haiku) for answer gen |
| File storage | Local volume (MVP) | Raw files before text extraction; S3 in Phase-2 |

## 3. Data model
| Table | Columns | Indexes / Constraints |
|-------|---------|-----------------------|
| `users` | `id uuid PK`, `username text UNIQUE`, `hashed_password text`, `role text`, `is_active bool`, `created_at timestamptz` | idx on `username`; role CHECK IN ('employee','contributor','admin') |
| `collections` | `id uuid PK`, `name text UNIQUE`, `description text`, `created_by uuid FK users`, `created_at timestamptz`, `updated_at timestamptz` | UNIQUE(name) |
| `documents` | `id uuid PK`, `collection_id uuid FK collections`, `filename text`, `file_type text`, `status text`, `uploaded_by uuid FK users`, `uploaded_at timestamptz`, `updated_at timestamptz`, `error_message text` | idx on `collection_id`; status CHECK IN ('waiting','processing','ready','failed') |
| `document_chunks` | `id uuid PK`, `document_id uuid FK documents`, `chunk_index int`, `chunk_text text`, `embedding vector(1024)` | ivfflat idx on `embedding vector_cosine_ops`; idx on `document_id` |
| `faq_topics` | `id uuid PK`, `label text UNIQUE`, `created_by uuid FK users`, `created_at timestamptz`, `updated_at timestamptz` | UNIQUE(label) |
| `audit_events` | `id uuid PK`, `user_id uuid FK users`, `role_at_time text`, `action_type text`, `resource_type text`, `resource_id uuid`, `resource_name text`, `outcome text`, `question_excerpt varchar(100)`, `timestamp timestamptz` | idx on `timestamp`; idx on `user_id` |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | `/auth/token` | `{username, password}` | `{access_token, token_type, role}` | Returns JWT; 401 on bad creds |
| GET | `/api/v1/collections` | — | `[{id, name, description}]` | All roles |
| POST | `/api/v1/collections` | `{name, description?}` | `{id, name}` | contributor/admin; 409 on dup name |
| PATCH | `/api/v1/collections/{id}` | `{name?, description?}` | `{id, name}` | contributor/admin |
| POST | `/api/v1/collections/{id}/documents` | multipart `file` | `{id, filename, status}` | contributor/admin; 422 bad type/size |
| GET | `/api/v1/collections/{id}/documents` | — | `[{id, filename, status, uploaded_at, uploader}]` | All roles |
| POST | `/api/v1/collections/{id}/ask` | `{question}` | `{answer, citations:[{filename,snippet}]}` | All roles; RAG pipeline |
| GET | `/api/v1/faq-topics` | — | `[{id, label}]` | All roles |
| POST | `/api/v1/faq-topics` | `{label}` | `{id, label}` | contributor/admin |
| GET | `/api/v1/audit` | `?page&page_size&action_type&from_date&to_date` | `{items:[...], total}` | admin only; 403 others |

## 5. Rules
- **Auth / JWT (FR-1, NFR-1):** `/auth/token` issues JWT (PyJWT, 8-hour TTL env `JWT_TTL_HOURS`); all routes except `/health` use `Depends(get_current_user)`; 401 on missing/expired token; Streamlit: `login_form()` gates all views on `st.session_state.token`; token sent as `Authorization: Bearer` on every `httpx` call.
- **RBAC (FR-2, NFR-2):** role embedded in JWT claims; `Depends(require_role(['contributor','admin']))` on collection write, document upload, FAQ write; `Depends(require_role(['admin']))` on `/audit`; 403 on violation; Streamlit: tabs scoped — employee=collections+chat, contributor+=upload+doc list+FAQ, admin+=audit.
- **Grounded RAG only (FR-6):** retrieval prompt instructs Claude to answer solely from provided `chunk_text` context; if no chunks exceed cosine similarity threshold (0.75) or model cannot ground answer → return exact string `"Not found in documents"`; never allow free-form generation outside context.
- **Document processing pipeline (FR-4, NFR-5):** on upload set `status=waiting`; background task (FastAPI `BackgroundTasks`) extracts text → chunks (~500 tokens, ~50 overlap) → Titan embed → insert `document_chunks` → set `status=ready`; on error set `status=failed` + `error_message`; file size > 20 MB → 422 before write; unsupported MIME → 422.
- **Audit trail (FR-8, NFR-9, NFR-11):** every upload + Q&A event writes to `audit_events` in a `finally`-guarded service call; `question_excerpt` truncated to 100 chars; full question text never logged; records retained ≥ 90 days (DB-level retention policy note in migration comments).
- **Collection uniqueness & deletion guard (FR-3):** `UNIQUE` constraint on `collections.name`; API returns 409 on duplicate; `DELETE /collections/{id}` rejected with 409 if any document row references it (FK + guard in service layer).
- **Input validation (NFR-5):** file upload validated for MIME type (allowed: `application/pdf`, `text/plain`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`) and size ≤ 20 MB at API boundary before any DB write.
- **Structured logging (NFR-8):** middleware emits JSON per request: `{timestamp, request_id, user_id, role, method, path, status_code, latency_ms}`; errors include stack trace at ERROR level; background jobs log `{doc_id, collection_id, step, duration_ms, status}`.

## 6. DB delivery
1. Migration order: `001_enable_pgvector.sql`, `002_create_users.sql`, `003_create_collections.sql`, `004_create_documents.sql`, `005_create_document_chunks.sql`, `006_create_faq_topics.sql`, `007_create_audit_events.sql`
2. Seed data (`scripts/seed_demo.py`): 1 admin (`admin`/`AdminPass1!`), 1 contributor (`hr_contributor`/`HrPass1!`), 1 employee (`employee1`/`EmpPass1!`); 1 collection `"2026 Benefits Demo"`; 1 pre-chunked `ready` document (synthetic benefits PDF with known Q&A pairs); 2 FAQ topics: `"Enrollment"`, `"Dental"`.
3. Athena / NoSQL: not used.
