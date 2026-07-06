# Platform Desk (Runbook Vector Desk) — Solution Design

## 1. Summary
Runbook Vector Desk is an internal SRE operations tool that ingests structured runbooks (decomposed into ordered steps), embeds step body text for semantic search, and exposes a role-gated on-call console. FastAPI serves all business logic and RBAC; Postgres stores structured metadata; ChromaDB (local) holds vector embeddings; Streamlit provides the UI. TBD: confidence-score threshold value, one-liner summary generation mechanism (excerpt vs. LLM). Diagram: `docs/generated-diagrams/platform-desk.png`

---

## 2. Stack
| Layer | Technology | Notes |
|-------|------------|-------|
| UI | Streamlit | `ui/streamlit_app.py` calls FastAPI over HTTP (port 8501) |
| API | FastAPI | `target-apps/platform-desk/app/`; `/api/v1/` prefix |
| Auth | API Key (`X-API-Key`) | Header check via `.env`; role embedded in key record |
| DB | PostgreSQL | Structured metadata; local Docker or RDS |
| Vector Store | ChromaDB (local) | Embeds `RunbookStep.body_text`; sentence-transformers model |
| Storage | Local filesystem | Evidence/files at `data/evidence/`; no S3 for MVP |

---

## 3. Data model
| Table | Columns | Indexes / Constraints |
|-------|---------|----------------------|
| `services` | `id uuid PK`, `name text UNIQUE`, `owning_team text`, `criticality_tier int`, `active_support bool`, `created_at timestamptz` | `idx_services_name`; `criticality_tier IN (1,2,3)` |
| `runbooks` | `id uuid PK`, `title text`, `service_id uuid FK→services`, `default_severity text`, `short_summary text`, `author text`, `lifecycle_status text`, `created_at timestamptz`, `updated_at timestamptz` | `idx_runbooks_service_status`; `lifecycle_status IN ('draft','active','retired')`; UNIQUE(`title`,`service_id`) WHERE `lifecycle_status='active'` |
| `runbook_steps` | `id uuid PK`, `runbook_id uuid FK→runbooks`, `step_number int`, `title text`, `body_text text`, `estimated_minutes int NULL`, `warning_callout text NULL` | `idx_steps_runbook`; UNIQUE(`runbook_id`,`step_number`) |
| `incident_touches` | `id uuid PK`, `runbook_id uuid FK→runbooks`, `step_number int NULL`, `ticket_reference text NOT NULL`, `notes text NULL`, `role text`, `created_at timestamptz` | `idx_touches_runbook_created` |
| `search_events` | `id uuid PK`, `query_text varchar(500)`, `service_filter_id uuid NULL FK→services`, `result_count int`, `top_score float`, `response_time_ms int`, `created_at timestamptz` | `idx_search_created` |
| `api_keys` | `id uuid PK`, `key_hash text UNIQUE`, `role text`, `label text`, `active bool`, `created_at timestamptz` | `role IN ('viewer','editor','admin')`; `idx_apikeys_hash` |

---

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | `/health` | — | `{status, version}` | Unauthenticated (FR-3/NFR-4) |
| GET/POST/PUT/DELETE | `/api/v1/services` / `/{id}` | `{name,owning_team,criticality_tier,active_support}` | `ServiceOut` / list | Admin only; 409 on dup name (FR-1) |
| GET/POST | `/api/v1/runbooks` / `/{id}` | `{title,service_id,default_severity,short_summary,author}` | `RunbookOut` / list | Editor+ create; all auth browse active (FR-2,FR-14) |
| POST | `/api/v1/runbooks/{id}/activate` | — | `{status, similar_runbooks[]}` | Editor+; 422 if 0 steps; 409 on title+service conflict; returns advisory similar list (FR-2,FR-3,FR-8) |
| POST | `/api/v1/runbooks/{id}/retire` | — | `RunbookOut` | Editor+; sync removes steps from vector index (FR-7) |
| GET/POST/PUT/DELETE | `/api/v1/runbooks/{id}/steps` / `/{step_id}` | `{step_number,title,body_text,estimated_minutes,warning_callout}` | `StepOut` / list | Editor+; atomic reorder on POST reorder sub-path (FR-4) |
| POST | `/api/v1/search` | `{query:str, service_id?:uuid, top_k?:int}` | `{results:[{service_name,runbook_title,step_number,excerpt,summary,score}]}` | All auth; one result/runbook; FR-5,FR-6,FR-15; logs SearchEvent |
| POST | `/api/v1/incident-touches` | `{runbook_id,ticket_reference,step_number?,notes?}` | `TouchOut 201` | Viewer+; 422 if no ticket_ref (FR-9) |
| GET | `/api/v1/admin/report/reliance` | `?days=30` | `[{service_name,touch_count}]` | Admin only; no PII (FR-10) |
| GET/POST | `/api/v1/admin/analytics` / `/index-refresh` | `?top_n=25` / — | `{top_queries,weak_match_queries,response_time_stats}` / `{status,steps_indexed}` | Admin only (FR-11,FR-12) |

---

## 5. Rules
- **Auth**: All routes except `GET /health` require `X-API-Key` header; missing/invalid → 401 (NFR-4).
- **RBAC**: `viewer` → search, browse, incident touch; `editor` → viewer + runbook/step CRUD + activate/retire; `admin` → editor + service catalog + analytics + index refresh; wrong role → 403 (NFR-5, FR-13).
- **Activation guard**: Reject activation if `runbook_steps` count = 0 (422); reject if unique active-title constraint violated (409) (FR-2, FR-3).
- **Retirement sync**: On retire, delete all step vectors from ChromaDB within same request before committing status change (FR-7).
- **Incremental indexing**: On step save/update and runbook activation, upsert vector(s) in ChromaDB; Admin refresh re-indexes full active corpus (FR-12).
- **Analytics privacy**: `search_events` and `incident_touches` store no `user_id`/email; `role` (string) only (NFR-6, NFR-8, NFR-9).
- **Low-confidence disclosure**: If `top_score < CONFIDENCE_THRESHOLD` (env var, default 0.45), set `summary = "Confidence is low — review steps carefully"` (FR-15).
- **Ticket reference required**: `POST /incident-touches` with missing `ticket_reference` → 422, no record created (FR-9).

---

## 6. DB delivery
1. Migration order: `001_create_services.sql`, `002_create_runbooks.sql`, `003_create_runbook_steps.sql`, `004_create_incident_touches.sql`, `005_create_search_events.sql`, `006_create_api_keys.sql`
2. Seed data (`seed.py`): 8–10 services (varied teams + criticality tiers); 12–15 runbooks (mix of draft/active/retired); 60+ steps with realistic body text covering Redis, Kafka, DB connection topics; 3 api_key rows (one per role); 20+ search_events; 15+ incident_touches — sufficient for FR-11 analytics and FR-8 similarity demo.
