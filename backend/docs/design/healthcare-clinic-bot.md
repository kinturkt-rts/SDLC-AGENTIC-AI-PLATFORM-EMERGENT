# Healthcare Clinic Assistant — Solution Design

## 1. Summary
A Streamlit + FastAPI demo chatbot that answers clinic FAQ questions grounded in Postgres-stored entries via AWS Bedrock. Single-clinic MVP; no HIPAA scope, no booking integrations, no vector DB. TBD: Bedrock model selection, exact disclaimer wording, FAQ relevance threshold.
`Diagram: docs/diagrams/generated-diagrams/healthcare-clinic-bot.png`

## 2. Stack
| Layer | Technology |
|-------|------------|
| UI | Streamlit (Chat, FAQ Browser, Admin pages) |
| API | FastAPI + Uvicorn (`target-apps/healthcare-clinic-bot/`) |
| ORM / DB | SQLAlchemy + psycopg2, Alembic migrations, RDS Postgres |
| AI | AWS Bedrock (boto3) — Claude variant |
| Auth | Seeded `users` table, bcrypt, JWT bearer token |
| Config | `python-dotenv`; secrets via env vars only |

## 3. Data model
| Table | Columns | Indexes / Constraints |
|---|---|---|
| `users` | `id uuid PK`, `username varchar(80) UNIQUE`, `hashed_password text`, `role varchar(20)`, `created_at timestamptz` | `idx_users_username` |
| `faq_entries` | `id serial PK`, `category varchar(60)`, `question text`, `answer text`, `is_active bool DEFAULT true`, `search_vector tsvector`, `created_at timestamptz`, `updated_at timestamptz` | `idx_faq_tsv` GIN on `search_vector`; `updated_at` trigger |
| `chat_sessions` | `id uuid PK`, `session_label varchar(120)`, `created_at timestamptz` | `idx_sessions_created` |
| `chat_messages` | `id serial PK`, `session_id uuid FK→chat_sessions.id`, `role varchar(10)`, `content text`, `is_fallback bool DEFAULT false`, `created_at timestamptz` | `idx_msgs_session_id`; CHECK `role IN ('user','assistant')` |

## 4. API surface
| Method | Path | Request | Response | Notes |
|---|---|---|---|---|
| POST | `/auth/login` | `{username: str, password: str}` | `{access_token: str, token_type: str}` | Returns JWT; FR-8, NFR-4 |
| POST | `/chat/sessions` | `{session_label?: str}` | `{session_id: uuid, created_at: datetime}` | Creates session; FR-5 |
| POST | `/chat/message` | `{session_id: uuid, message: str}` | `{session_id: uuid, reply: str, disclaimer: str, is_fallback: bool}` | Core flow; FR-1–FR-4 |
| GET | `/chat/sessions/{session_id}/messages` | — | `[{role, content, is_fallback, created_at}]` | FR-5, FR-9 |
| GET | `/faqs` | `?category=str&active=bool` | `[{id, category, question, answer, is_active}]` | Public; FR-6 |
| POST | `/faqs` | `{category: str, question: str, answer: str}` | `{id: int, …}` | Staff only; FR-7 |
| PUT | `/faqs/{faq_id}` | `{question?: str, answer?: str, category?: str, is_active?: bool}` | `{id: int, …}` | Staff only; FR-7 |
| GET | `/admin/stats` | — | `{total_faqs: int, total_sessions: int, total_messages: int, fallback_rate: float}` | Staff only; FR-8 |

## 5. Rules
- **Auth / RBAC:** `POST /auth/login` is public. All `/faqs` write routes and `/admin/*` require `role=staff` JWT. `/chat/*` and `GET /faqs` are unauthenticated. Unauthenticated write requests → HTTP 401 (NFR-4).
- **Sensitive-data guard:** Regex pre-check on `message` for SSN pattern (`\d{3}-\d{2}-\d{4}`), DOB keywords, symptom/prescription keywords → return redirect-to-clinic response; nothing written to `chat_messages.content` (FR-4, NFR-3).
- **Disclaimer:** Hardcoded constant appended server-side to every `/chat/message` response; not togglable (FR-2, NFR-11).
- **Fallback logic:** Postgres `tsvector` full-text search on `faq_entries`; if zero rows returned with `ts_rank ≥ threshold` → `is_fallback=true`; Bedrock NOT called for fallback path (FR-3).
- **Bedrock grounding:** Pass ≤ 30 active FAQ entries as context; prompt instructs model to answer only from supplied context (FR-1, NFR-8).
- **Logging:** Structured JSON to stdout — `timestamp, method, path, session_id, status, latency_ms`; Bedrock calls add `faq_count, model_id, bedrock_latency_ms` (NFR-8); no PII in logs.
- **No sensitive columns:** Schema contains no SSN, DOB, or symptom fields by design (NFR-3).

## 6. DB delivery
1. Migration order: `001_create_users.sql`, `002_create_faq_entries.sql`, `003_create_chat_sessions.sql`, `004_create_chat_messages.sql`, `005_add_faq_tsvector_trigger.sql`
2. Seed data (`seed_dev.sql`): 1 staff user (`admin` / bcrypt-hashed `changeme`); ≥ 5 FAQ entries across 3 categories — `office_hours` (2 entries), `insurance` (2 entries), `parking_booking` (2 entries) — covering FR-10 topics.
3. Alembic `env.py` reads `DATABASE_URL` from env; `alembic upgrade head` + `psql -f seed_dev.sql` is the full local setup.
