# Facility Work Order Hub — Solution Design

## 1. Summary
Internal facility management REST API (FastAPI) with a Streamlit front-end for creating, assigning, and tracking maintenance work orders across multi-site portfolios. Primary store is PostgreSQL; auth is JWT Bearer (PyJWT, 60-min TTL). Diagram: `docs/generated-diagrams/facility-work-order-hub.png`
TBD: deployment target (Docker Compose vs. PaaS); JWT TTL for production; technician concurrent-order cap.

## 2. Stack
| Layer | Technology | Path / Notes |
|-------|-----------|--------------|
| UI | Streamlit | `ui/streamlit_app.py` — calls FastAPI over HTTP (port 8501); never imports from `app/` |
| API | FastAPI + Uvicorn | `target-apps/facility-work-order-hub/app/`; routes prefixed `/api/v1/` |
| Auth | PyJWT + passlib[bcrypt] | `SECRET_KEY` from `.env`; bcrypt cost 12; 60-min TTL |
| ORM / Migrations | SQLAlchemy 2.x + Alembic | `alembic/versions/` inside service root |
| Database | PostgreSQL (Docker) | SQLite acceptable for single-user demo |
| Evidence / Files | Local filesystem | `data/evidence/` — no S3 in MVP |

## 3. Data model
| Table | Columns | Indexes / Constraints |
|-------|---------|-----------------------|
| `users` | `id uuid PK`, `email text UNIQUE`, `hashed_password text`, `display_name text`, `role user_role_enum`, `created_at timestamptz` | idx on `email`, `role` |
| `sites` | `id uuid PK`, `site_code text UNIQUE`, `name text`, `address_line text`, `active bool DEFAULT true`, `created_at timestamptz`, `updated_at timestamptz` | idx on `active` |
| `locations` | `id uuid PK`, `site_id uuid FK(sites)`, `floor text`, `area_label text NULL`, `created_at timestamptz` | idx on `site_id` |
| `work_orders` | `id uuid PK`, `title text`, `description text`, `category wo_category_enum`, `priority wo_priority_enum`, `status wo_status_enum`, `requester_id uuid FK(users)`, `assignee_id uuid FK(users) NULL`, `site_id uuid FK(sites)`, `location_id uuid FK(locations) NULL`, `due_by timestamptz NULL`, `reopen_reason text NULL`, `created_at timestamptz`, `updated_at timestamptz`, `assigned_at timestamptz NULL`, `started_at timestamptz NULL`, `completed_at timestamptz NULL`, `closed_at timestamptz NULL` | idx on `site_id`, `assignee_id`, `status`, `due_by` |
| `work_order_status_history` | `id uuid PK`, `work_order_id uuid FK(work_orders)`, `from_status wo_status_enum NULL`, `to_status wo_status_enum`, `changed_by_user_id uuid FK(users)`, `changed_at timestamptz`, `reason text NULL` | idx on `work_order_id`; append-only |
| `comments` | `id uuid PK`, `work_order_id uuid FK(work_orders)`, `author_id uuid FK(users)`, `body text`, `created_at timestamptz` | idx on `work_order_id`; no UPDATE/DELETE |

**Enums:** `user_role_enum` = requester|technician|facilities_admin|leadership; `wo_category_enum` = HVAC|plumbing|electrical|access|general; `wo_priority_enum` = low|normal|urgent; `wo_status_enum` = submitted|triaged|assigned|in_progress|completed|closed

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | `/api/v1/auth/token` | `{email, password}` | `{access_token, token_type}` | FR-1; no auth required |
| GET | `/health` | — | `{status:"ok"}` | FR-16; no auth |
| POST | `/api/v1/sites` | `{site_code, name, address_line, active?}` | `SiteOut` 201 | FR-3; admin only |
| PATCH | `/api/v1/sites/{site_id}` | `{name?, address_line?, active?}` | `SiteOut` | FR-3; admin only |
| POST | `/api/v1/sites/{site_id}/locations` | `{floor, area_label?}` | `LocationOut` 201 | FR-4; admin only |
| POST | `/api/v1/work-orders` | `{title, description, category, priority, site_id, location_id?, due_by?}` | `WorkOrderOut` 201 | FR-5; requester/admin; warns if urgent+no due_by |
| GET | `/api/v1/work-orders` | `?page&page_size&status&site_id` | `Page[WorkOrderOut]` | FR-8; scoped by role |
| GET | `/api/v1/work-orders/{id}` | — | `WorkOrderOut` (incl. `is_overdue`) | FR-10, FR-13 |
| PATCH | `/api/v1/work-orders/{id}/status` | `{status, reason?}` | `WorkOrderOut` | FR-6; role/ownership guards |
| PATCH | `/api/v1/work-orders/{id}/assign` | `{assignee_id}` | `WorkOrderOut` | FR-7; admin only |
| POST | `/api/v1/work-orders/{id}/comments` | `{body}` | `CommentOut` 201 | FR-9; read-access check |
| GET | `/api/v1/work-orders/{id}/comments` | — | `list[CommentOut]` | NFR-5; leadership sees display_name only |
| GET | `/api/v1/dashboard/sla` | — | `{open_count, closed_count, overdue_count, avg_days_to_close_by_category, top_sites}` | FR-11; leadership/admin |
| GET | `/api/v1/dashboard/workload` | — | `list[{technician_id, display_name, open_count}]` | FR-12; admin only |

## 5. Rules
- **Auth:** All routes except `/health` and `POST /auth/token` require `Authorization: Bearer <jwt>`; 401 on missing/invalid/expired token (NFR-4).
- **RBAC:** requester → create WO + read own + comment own; technician → read assigned + transition assigned→in_progress→completed + comment; facilities_admin → all WO ops + sites/locations CRUD + assign + workload view; leadership → read-all + dashboard only. Return 403 on violation (FR-2).
- **Status transitions:** Enforced in service layer; invalid transition → 422. Reopen (closed→in_progress) requires non-empty `reason` (FR-6). Force-close (admin only, any→closed, `force_close=true`) (FR-6).
- **`is_overdue`:** Computed dynamically: `due_by IS NOT NULL AND due_by < now() AND status != 'closed'` — never stored (FR-10, NFR-7).
- **Timestamp immutability:** `created_at`, `assigned_at`, etc. set once at transition; PATCH body fields for these are ignored/rejected (NFR-9).
- **Inactive site guard:** WO creation with inactive `site_id` → 422 (FR-3, FR-5).
- **Leadership PII guard:** `CommentOut` for leadership role strips `author_id`/`email`; returns `author_display_name` only (NFR-5).
- **Pagination:** default `page_size=20`, max 100; sorted by `created_at DESC` (FR-8).

## 6. DB delivery
1. **Migration order:** `001_create_enums.sql`, `002_users.sql`, `003_sites.sql`, `004_locations.sql`, `005_work_orders.sql`, `006_work_order_status_history.sql`, `007_comments.sql`, `008_indexes.sql`
2. **Seed data (`scripts/seed.py`):** 3 active sites × 2–3 locations; 6 users (2 requesters, 2 technicians, 1 admin, 1 leadership) — all with password `DevPassword123!` (bcrypt, documented in seed SQL comment); ≥ 8 work orders across all statuses, 2 with `due_by` in the past (overdue), 1 with status `in_progress` after reopen; comments on ≥ 4 orders; timestamps spread over 60 days. Guard: `assert os.getenv("APP_ENV") == "development"`.
3. **NoSQL / Athena:** Not used in MVP.
