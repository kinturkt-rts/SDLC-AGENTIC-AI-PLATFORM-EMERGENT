# Change Request Hub — Solution Design

## 1. Summary
Role-aware change management web app: requesters draft changes, managers approve/schedule, implementers execute, leadership reads dashboards. Primary DB is PostgreSQL; API is FastAPI REST (`/api/v1/`); Streamlit is the sole UI. JWT Bearer auth (HS256); append-only audit tables enforced at application layer.
`Diagram: docs/generated-diagrams/change-request-hub.png`
TBD: JWT algorithm for production (HS256 assumed), sub-path vs body-driven status transitions, emergency re-approval policy.

## 2. Stack
| Layer | Technology | Path / Notes |
|-------|------------|--------------|
| UI | Streamlit | `ui/streamlit_app.py` — HTTP client to FastAPI (port 8501); JWT stored in `st.session_state` |
| API | FastAPI ≥ 0.110 | `target-apps/change-request-hub/app/`; OpenAPI at `/docs` |
| Auth | PyJWT / python-jose HS256 | Secret from `JWT_SECRET_KEY` env var; 8 h TTL |
| ORM / Migrations | SQLAlchemy ≥ 2.0 + Alembic | `alembic/` under service root |
| Database | PostgreSQL ≥ 15 | TIMESTAMPTZ everywhere; Docker or RDS |
| File storage | Local filesystem | `data/evidence/` — no S3 in MVP |

## 3. Data model
| Table | Columns | Indexes / Constraints |
|-------|---------|-----------------------|
| `users` | `id UUID PK`, `email TEXT UNIQUE`, `password_hash TEXT`, `display_name TEXT`, `role TEXT` (requester\|manager\|implementer\|leadership), `active BOOL DEFAULT true`, `created_at TIMESTAMPTZ` | idx on `role`, `email` |
| `services` | `id UUID PK`, `name TEXT UNIQUE`, `owner_team TEXT`, `tier TEXT` (tier1\|tier2\|tier3), `active BOOL DEFAULT true`, `created_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ` | idx on `active` |
| `environments` | `id UUID PK`, `name TEXT UNIQUE`, `sort_order INT`, `active BOOL DEFAULT true`, `created_at TIMESTAMPTZ` | — |
| `blackout_windows` | `id UUID PK`, `environment_id UUID FK(environments)`, `start_at TIMESTAMPTZ`, `end_at TIMESTAMPTZ`, `reason TEXT`, `created_by UUID FK(users)`, `created_at TIMESTAMPTZ` | idx on `environment_id, start_at, end_at` |
| `change_requests` | `id UUID PK`, `title TEXT`, `description TEXT`, `service_id UUID FK(services)`, `target_environment_id UUID FK(environments)`, `change_type TEXT` (standard\|normal\|emergency), `risk TEXT` (low\|medium\|high\|critical), `status TEXT`, `requester_id UUID FK(users)`, `implementer_id UUID FK(users) NULL`, `planned_start TIMESTAMPTZ`, `planned_end TIMESTAMPTZ`, `rollback_plan TEXT`, `created_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ`, `submitted_at TIMESTAMPTZ NULL`, `approved_at TIMESTAMPTZ NULL`, `scheduled_at TIMESTAMPTZ NULL`, `started_at TIMESTAMPTZ NULL`, `completed_at TIMESTAMPTZ NULL`, `closed_at TIMESTAMPTZ NULL` | idx on `status`, `requester_id`, `implementer_id`, `planned_end`, `created_at`, `service_id`, `target_environment_id` |
| `approval_records` | `id UUID PK`, `change_id UUID FK(change_requests)`, `approver_id UUID FK(users)`, `decision TEXT` (approved\|rejected), `comment TEXT`, `decided_at TIMESTAMPTZ` | idx on `change_id`; no UPDATE/DELETE |
| `comments` | `id UUID PK`, `change_id UUID FK(change_requests)`, `author_id UUID FK(users)`, `body TEXT`, `posted_at TIMESTAMPTZ` | idx on `change_id`; no UPDATE/DELETE |
| `status_history` | `id UUID PK`, `change_id UUID FK(change_requests)`, `from_status TEXT NULL`, `to_status TEXT`, `actor_id UUID FK(users)`, `changed_at TIMESTAMPTZ`, `reason TEXT NULL` | idx on `change_id, changed_at`; append-only |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | `/api/v1/auth/token` | `{email, password}` | `{access_token, token_type}` | FR-1; no auth required |
| GET | `/health` | — | `{status:"ok"}` | FR-17; no auth |
| GET/POST | `/api/v1/services` | POST: `{name, owner_team, tier}` | 200 paginated list / 201 service | FR-2; POST=manager only |
| PATCH | `/api/v1/services/{id}` | `{name?, owner_team?, tier?, active?}` | 200 service | FR-2; manager only |
| GET/POST | `/api/v1/environments` | POST: `{name, sort_order}` | 200 list / 201 environment | FR-3; POST=manager |
| GET/POST | `/api/v1/blackout-windows` | POST: `{environment_id, start_at, end_at, reason}` | 200 list / 201 window | FR-3; GET accepts `?environment_id=` |
| GET/POST | `/api/v1/change-requests` | POST: `{title, description, service_id, target_environment_id, change_type, risk, planned_start, planned_end, rollback_plan}` | 200 paginated / 201 CR | FR-4, FR-11; role-scoped GET |
| GET | `/api/v1/change-requests/{id}` | — | CR + `approval_records` + `status_history` | FR-6, FR-9 |
| PATCH | `/api/v1/change-requests/{id}/status` | `{to_status, reason?, planned_start?, planned_end?}` | 200 CR | FR-5, FR-7; lifecycle guard |
| PATCH | `/api/v1/change-requests/{id}/assign` | `{implementer_id}` | 200 CR | FR-10; manager only |
| GET/POST | `/api/v1/change-requests/{id}/comments` | POST: `{body}` | 200 thread / 201 comment | FR-8; append-only |
| GET | `/api/v1/users` | `?role=implementer` | 200 user list | FR-10; all authenticated roles |
| GET | `/api/v1/dashboard/summary` | — | `{counts_by_status, counts_by_risk, overdue_scheduled_count, monthly_by_env, top_services, active_emergency_count}` | FR-12; manager+leadership |

## 5. Rules
- **Auth**: All routes except `/health` and `/api/v1/auth/token` require `Authorization: Bearer <JWT>`; missing/invalid → 401 (NFR-3).
- **RBAC**: manager-only: POST services/environments/blackout-windows, PATCH service, PATCH assign, PATCH status approve/reject/schedule/close, GET dashboard; implementer-only: PATCH status implementing→completed (own assigned only); requester: POST change-request, comment on own; leadership: GET dashboard + read-only change list. Server-side authoritative (NFR-4).
- **Status graph**: draft→submitted (requester|manager) → approved|rejected (manager) → scheduled (manager, blackout check) → implementing (implementer) → completed (assigned implementer) → closed (manager). Emergency shortcut: approved→implementing (FR-5). Any invalid edge → 422.
- **Blackout overlap**: On `scheduled` transition check `planned_start < bw.end_at AND planned_end > bw.start_at` for target environment; 422 with conflicting `blackout_window_id` and `reason` (FR-7).
- **Append-only**: No UPDATE/DELETE routes exist for `status_history` or `comments`; application guard + DB trigger in migration (NFR-8, FR-8, FR-9).
- **Passwords**: bcrypt cost ≥ 12; plaintext never logged (NFR-5).
- **Pagination**: All list endpoints accept `page` (default 1) and `page_size` (default 25, max 100); response includes `total` (NFR-9).
- **Structured logging**: JSON per request with `method, path, status_code, duration_ms, user_id` (NFR-10); no email/display_name in logs.

## 6. DB delivery
1. **Migration order**: `001_create_users.sql`, `002_create_services.sql`, `003_create_environments.sql`, `004_create_blackout_windows.sql`, `005_create_change_requests.sql`, `006_create_approval_records.sql`, `007_create_comments.sql`, `008_create_status_history.sql`, `009_add_indexes.sql`, `010_add_immutability_triggers.sql`
2. **Seed data** (`scripts/seed.py` or `seed.sql`): 6 users (2 requesters, 2 implementers, 1 manager, 1 leadership) all with bcrypt hash of `ChangeMe123!` (documented in SQL comment); 6 services (2×tier1, 2×tier2, 2×tier3); 3 environments (dev, staging, prod); 2 blackout windows (1 active on prod); ≥ 10 change requests covering all statuses incl. 1 rejected, 1 emergency, 2 overdue scheduled; approval rows on ≥ 5 changes; comments on ≥ 4; full status_history on all non-draft; timestamps spanning 90 days (FR-18).
3. **Athena / NoSQL**: not used in MVP.
