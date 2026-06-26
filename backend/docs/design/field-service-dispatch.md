# Field Service Dispatch — Solution Design

## 1. Summary
FastAPI REST service + Streamlit UI replacing whiteboard dispatch for a 15-tech HVAC shop. PostgreSQL (prod) / SQLite (dev) via SQLAlchemy; JWT RBAC for Dispatcher, Technician, Owner roles. Diagram: `docs/diagrams/generated-diagrams/field-service-dispatch.png`
TBD: SLA breach threshold hour (FR-7); skill enum list (FR-3); parts-post-completion lock confirmation.

## 2. Stack
| Layer | Technology | Path |
|-------|------------|------|
| UI | Streamlit | `ui/streamlit_app.py` + `ui/pages/`; calls FastAPI over HTTP (port 8501) |
| API | FastAPI + Uvicorn | `target-apps/field-service-dispatch/app/` |
| Auth | python-jose JWT | 8 h expiry, role in claims; `NFR-3/4` |
| ORM | SQLAlchemy 2.x | SQLite dev → PostgreSQL prod via `DATABASE_URL` |
| Cache | ElastiCache (Redis) | Low-latency board/status reads; `NFR-1` |
| Storage | S3 | Job attachments/photos (post-MVP upload path) |

## 3. Data model
| Table | Columns | Indexes / constraints |
|-------|---------|-----------------------|
| `users` | `id uuid PK`, `username text UNIQUE`, `hashed_password text`, `role text`, `technician_id uuid FK(technicians) NULL` | idx on `username` |
| `customers` | `id uuid PK`, `full_name text`, `phone text`, `email text NULL`, `is_active bool DEFAULT true`, `created_at timestamptz` | idx on `is_active` |
| `service_addresses` | `id uuid PK`, `customer_id uuid FK(customers)`, `street text`, `city text`, `state text`, `postal_code text` | idx on `customer_id` |
| `technicians` | `id uuid PK`, `display_name text`, `skills text[]`, `is_active bool DEFAULT true` | idx on `is_active` |
| `work_orders` | `id uuid PK`, `customer_id uuid FK(customers)`, `description text`, `priority text CHECK(routine,urgent)`, `scheduled_date date`, `time_window text CHECK(morning,afternoon,all_day)`, `status text CHECK(new,assigned,in_progress,completed,cancelled)`, `assigned_technician_id uuid FK(technicians) NULL`, `completion_notes text NULL`, `created_at timestamptz`, `updated_at timestamptz` | idx on `(scheduled_date, status)`, idx on `assigned_technician_id` |
| `work_order_parts` | `id uuid PK`, `work_order_id uuid FK(work_orders)`, `part_name text`, `quantity int CHECK(>0)`, `unit_cost numeric(10,2) NULL` | idx on `work_order_id` |
| `status_history` | `id uuid PK`, `work_order_id uuid FK(work_orders)`, `actor_user_id uuid FK(users)`, `actor_role text`, `previous_status text NULL`, `new_status text`, `context_note text NULL`, `changed_at timestamptz` | idx on `(work_order_id, changed_at)`; **no UPDATE/DELETE** |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | `/auth/token` | `username`, `password` (form) | `{access_token, token_type, role}` | Public; `FR-15`-adjacent |
| GET | `/health` | — | `{status:"ok"}` | Public; `FR-15` |
| POST | `/customers` | `full_name`, `phone`, `email?`, `service_addresses[]` | `CustomerOut` | Dispatcher only; `FR-1` |
| GET/PATCH | `/customers/{id}` | PATCH: partial fields | `CustomerOut` | Dispatcher+Owner GET; `FR-1` |
| POST | `/work-orders` | `customer_id`, `description`, `priority`, `scheduled_date`, `time_window` | `WorkOrderOut` | Dispatcher; `FR-2` |
| PATCH | `/work-orders/{id}` | `status?`, `assigned_technician_id?`, `completion_notes?`, `parts?[]`, `addendum?` | `WorkOrderOut` | Role+state guards; `FR-2,4,5,6,11` |
| GET | `/work-orders/{id}/history` | — | `HistoryEntry[]` | All roles; `FR-8` |
| GET | `/technicians` | `active_only=true` | `Technician[]` | All roles; `FR-3` |
| GET | `/board` | `date=today` | `{unassigned[], technician_columns{}, sla_breaches[]}` | All roles; `FR-7` |
| GET | `/workload` | `date=today` | `{technician_id, total_assigned, in_progress_count, completed_count, sla_breach_flag}[]` | Owner+Dispatcher; `FR-10` |

## 5. Rules
- **Auth:** `POST /auth/token` and `GET /health` are public. All other routes require `Authorization: Bearer <jwt>`. Return 401 on missing/expired token (`NFR-3`).
- **RBAC — Dispatcher:** full CRUD on customers, work-orders (create/reschedule/cancel/assign/reassign/addendum), read all. `FR-2,4,11`
- **RBAC — Technician:** GET `/board` (own orders filtered), PATCH `/work-orders/{id}` for own assignments only (`assigned→in_progress`, `in_progress→completed`); 403 on others' orders. `FR-5`
- **RBAC — Owner:** GET on all endpoints; 403 on any mutating endpoint. `FR-9`
- **State guards:** Reject assignment if status ≠ `new`/`assigned`; reject completion without `completion_notes`; reject cancel on `completed` → HTTP 409. `FR-2,4,6`
- **Immutable history:** `status_history` has no DELETE or UPDATE route; insert-only via service layer. `NFR-10`
- **Completion lock:** Completed orders reject all PATCH fields except `addendum`; addendum appends (not replaces) with timestamp prefix. `FR-11`
- **SLA breach:** Urgent orders where `scheduled_date ≤ today` and `status NOT IN (completed, cancelled)` past `SLA_BREACH_HOUR` env var (default 17). `FR-7, NFR-9`

## 6. DB delivery
1. Migration order: `001_users.sql`, `002_customers_addresses.sql`, `003_technicians.sql`, `004_work_orders.sql`, `005_work_order_parts.sql`, `006_status_history.sql`
2. Seed (`scripts/seed.py`, idempotent, respects `DEMO_DATE` env var): 5 technicians (varied skills/active flags), 8 customers, 15 work orders (all statuses, ≥1 SLA-breached urgent, ≥2 completed with parts, mix assigned/unassigned), consistent assignment + history rows. `FR-14`
3. NoSQL/Athena: not used at MVP.
