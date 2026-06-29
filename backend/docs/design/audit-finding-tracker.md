# Audit Finding Tracker — Solution Design

## 1. Summary
Internal FastAPI + Streamlit tool for auditors to create, track, and remediate audit findings with immutable status history and file evidence. Postgres (SQLAlchemy/Alembic) is the primary DB; REST API with JWT auth. TBD: max evidence file size, data retention period, compliance framework specifics.

## 2. Stack
| Layer | Technology | Path / Notes |
|-------|-----------|--------------|
| UI | Streamlit | `ui/streamlit_app.py` — calls FastAPI over HTTP (port 8501) |
| API | FastAPI + Uvicorn | `target-apps/audit-finding-tracker/app/main.py` |
| Auth | JWT (PyJWT) | Bearer token; roles: auditor / assignee / executive |
| Database | PostgreSQL + SQLAlchemy + Alembic | Docker locally; RDS-compatible |
| Evidence | Local filesystem `data/evidence/<finding_id>/` | Path recorded in DB |
| Config | python-dotenv `.env` | `DATABASE_URL`, `JWT_SECRET`, `EVIDENCE_DIR` |

## 3. Data model
| Table | Columns | Indexes / Constraints |
|-------|---------|-----------------------|
| `users` | `id UUID PK`, `email VARCHAR(255) UNIQUE`, `hashed_password TEXT`, `role ENUM(auditor,assignee,executive)`, `created_at TIMESTAMPTZ` | idx on `email`, `role` |
| `audits` | `id UUID PK`, `title VARCHAR(255)`, `description TEXT`, `owner_id UUID FK→users.id`, `created_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ` | idx on `owner_id` |
| `findings` | `id UUID PK`, `audit_id UUID FK→audits.id`, `title VARCHAR(255)`, `description TEXT`, `severity ENUM(low,medium,high,critical)`, `status ENUM(open,in_progress,pending_verification,remediated,closed)`, `assignee_id UUID FK→users.id`, `due_date DATE`, `version INT DEFAULT 1`, `created_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ` | idx on `(status,severity,due_date)`, `assignee_id` |
| `status_history` | `id UUID PK`, `finding_id UUID FK→findings.id`, `actor_id UUID FK→users.id`, `from_status ENUM`, `to_status ENUM`, `comment TEXT`, `created_at TIMESTAMPTZ` | idx on `finding_id`; NO DELETE constraint |
| `evidence_files` | `id UUID PK`, `finding_id UUID FK→findings.id CASCADE DELETE`, `uploader_id UUID FK→users.id`, `filename VARCHAR(255)`, `file_path TEXT`, `uploaded_at TIMESTAMPTZ` | idx on `finding_id` |
| `comments` | `id UUID PK`, `finding_id UUID FK→findings.id`, `author_id UUID FK→users.id`, `body TEXT`, `created_at TIMESTAMPTZ` | idx on `finding_id` |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | `/api/v1/auth/login` | `{email, password}` | `{access_token, role}` | Returns JWT |
| GET | `/api/v1/audits` | — | `[{id, title, owner_id, created_at}]` | Auditor/executive only |
| POST | `/api/v1/audits` | `{title, description}` | `{id, title}` | Auditor only |
| GET | `/api/v1/findings` | `?status=&severity=&audit_id=` | `[Finding]` | Assignee sees own; auditor/exec sees all (FR-7) |
| POST | `/api/v1/findings` | `{audit_id, title, description, severity, assignee_id, due_date}` | `Finding` | Auditor only |
| PATCH | `/api/v1/findings/{id}` | `{status?, owner?, due_date?}` + `If-Match: version` | `Finding` | 409 on stale version (FR-5); 422 on invalid transition (FR-2) |
| GET | `/api/v1/findings/{id}/history` | — | `[StatusHistory]` | All roles |
| POST | `/api/v1/findings/{id}/evidence` | multipart `file` | `{id, filename}` | Required before `pending_verification` (FR-4) |
| GET | `/api/v1/reports/executive` | `?dept=&severity=` | `{overdue, by_severity, by_dept}` | Executive/auditor only (FR-6) |
| GET | `/api/v1/health` | — | `{status}` | No auth (NFR-3) |

## 5. Rules
- **Auth/RBAC (NFR-1, FR-7):** JWT Bearer on all routes except `/health`; `Depends(get_current_user)` + `Depends(require_role(...))` on protected routes; Streamlit: `st.session_state.token` gates all pages; tabs scoped: assignee=findings+evidence, auditor=+audits+reports, executive=reports only
- **Status transitions (FR-2):** Allowed: `open→in_progress→pending_verification→remediated→closed`, `open→closed`, any→`open` (reopen); API: transition guard in `finding_service.py` raises HTTP 422 on invalid move
- **Evidence gate (FR-4):** `pending_verification` transition blocked if `evidence_files` count = 0 for `finding_id`; enforced in `finding_service.validate_transition()`
- **Optimistic locking (FR-5):** PATCH reads `If-Match` header as int version; returns 409 if DB version ≠ header; increments version on save; Streamlit passes version from last GET
- **Immutable audit trail (FR-3, NFR-4, NFR-6):** Every status change appends to `status_history`; no UPDATE/DELETE permitted on that table; enforced via DB trigger `BEFORE UPDATE OR DELETE ON status_history → RAISE EXCEPTION`
- **Data scoping (FR-7):** `GET /findings` query filtered by `assignee_id = current_user.id` when role=assignee; auditor/executive get unfiltered; enforced in `findings.py` router
- **Executive reports (FR-6, NFR-2):** Aggregation queries on `findings` with indexes on `(status, severity, due_date)`; target <500 ms p95
- **Streamlit UI gates (NFR-1):** `login_form()` shown when token absent; sidebar hides auditor/executive tabs for assignees; finding status dropdown restricted to valid next-states client-side

## 6. DB delivery
1. Migration order: `001_create_users.sql`, `002_create_audits.sql`, `003_create_findings.sql`, `004_create_status_history.sql`, `005_create_evidence_files.sql`, `006_create_comments.sql`, `007_add_indexes.sql`, `008_status_history_immutability_trigger.sql`
2. Seed data: 3 users (1 auditor, 1 assignee, 1 executive), 2 audits, 12 findings spread across severities/statuses, sample status_history rows per finding (NFR-7)
3. Athena / NoSQL: not used
