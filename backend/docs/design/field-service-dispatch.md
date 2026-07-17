# Field Service Dispatch — Solution Design

## 1. Summary
Role-aware dispatch app replacing whiteboard/text workflow for a 15-tech HVAC shop. Postgres RDS stores customers, work orders, assignments, and audit logs; FastAPI serves all REST endpoints; Streamlit provides the Dispatcher board, Technician "My Jobs Today", and Owner read-only view. TBD: SLA cutoff timezone (env var `SLA_TZ`, default UTC); auth token lifetime assumed 24 h.

## 2. Stack
| Layer | Technology | Path |
|-------|------------|------|
| UI | Streamlit | `ui/streamlit_app.py` calls FastAPI over HTTP (port 8501) |
| API | FastAPI | `target-apps/field-service-dispatch/app/` |
| Auth | API-key → role lookup | `X-API-Key` header; role embedded in `users` table |
| ORM | SQLAlchemy + Alembic | models in `app/models.py` |
| DB | PostgreSQL (RDS single-AZ) | single instance, FK-constrained |
| Runtime | ECS (Docker Compose local) | `docker compose up` starts API + DB + UI |

## 3. Data model
| Table | Columns | Indexes / constraints |
|-------|---------|----------------------|
| `customers` | id uuid PK, full_name text, phone text, email text, street text, city text, state text, zip text, created_at timestamptz, deleted_at timestamptz | idx on deleted_at |
| `technicians` | id uuid PK, name text, skills text[], active bool DEFAULT true, created_at timestamptz | idx on active |
| `users` | id uuid PK, username text UNIQUE, hashed_password text, role text CHECK(role IN ('dispatcher','technician','owner')), technician_id uuid FK→technicians NULLABLE | idx on username |
| `work_orders` | id uuid PK, customer_id uuid FK→customers, description text, priority text CHECK(IN('routine','urgent')), scheduled_date date, time_window text CHECK(IN('morning','afternoon','all_day')), status text CHECK(IN('new','assigned','in_progress','completed','cancelled')), completion_notes text, dispatcher_addendum text, created_at timestamptz, updated_at timestamptz | idx on (scheduled_date, status), idx on status |
| `assignments` | id uuid PK, work_order_id uuid FK→work_orders UNIQUE, technician_id uuid FK→technicians, assigned_by uuid FK→users, assigned_at timestamptz, is_active bool DEFAULT true | UNIQUE(work_order_id) WHERE is_active=true (partial index) |
| `part_line_items` | id uuid PK, work_order_id uuid FK→work_orders, name text, quantity int CHECK(≥1), unit_cost numeric(10,2), created_at timestamptz | idx on work_order_id |
| `audit_log` | id uuid PK, work_order_id uuid FK→work_orders, from_status text, to_status text, actor_id uuid FK→users, actor_role text, changed_at timestamptz DEFAULT now() | idx on work_order_id; append-only |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | `/api/v1/auth/token` | `{username, password}` | `{access_token, role, technician_id}` | returns API key token |
| GET | `/health` | — | `{status:"ok"}` | no auth |
| POST/GET | `/api/v1/customers` | `{full_name,phone,email?,street,city,state,zip}` / — | `Customer` / `Customer[]` | dispatcher only write |
| PUT/DELETE | `/api/v1/customers/{id}` | partial fields / — | `Customer` / 204 | soft-delete sets deleted_at |
| POST/GET | `/api/v1/technicians` | `{name,skills[],active}` / — | `Technician` / `Technician[]` | dispatcher write |
| POST/GET | `/api/v1/work-orders` | `{customer_id,description,priority,scheduled_date,time_window}` / `?date=` | `WorkOrder` / `WorkOrder[]` | dispatcher creates |
| PATCH | `/api/v1/work-orders/{id}/status` | `{status, completion_notes?, parts?:[{name,quantity,unit_cost?}]}` | `WorkOrder` | enforces state machine |
| POST | `/api/v1/assignments` | `{work_order_id, technician_id}` | `Assignment` | dispatcher only; 409 if active exists |
| GET | `/api/v1/board` | `?date=YYYY-MM-DD` | `{unassigned[], technicians[], sla_breaches[]}` | dispatcher+owner |
| GET | `/api/v1/work-orders/{id}/audit-log` | — | `AuditLog[]` | dispatcher+owner; technician→403 |

## 5. Rules
- **Auth (FR-10, NFR-3):** `X-API-Key` resolved to `users` row; missing key→401; `Depends(get_current_user)` on all routes except `/health`; Streamlit: `login_form()` gates all views on `st.session_state.token` absent.
- **RBAC (FR-10, NFR-3):** roles=dispatcher/technician/owner; `Depends(require_role(*roles))` on each router; owner→GET only, 403 on POST/PUT/PATCH/DELETE; Streamlit tabs: dispatcher=full board+actions, technician=My Jobs Today+status buttons, owner=read-only board.
- **Status machine (FR-2, FR-5):** allowed transitions enforced in `app/services/work_order.py`; illegal→409; terminal states (`completed`,`cancelled`) locked→422; technician may only advance own order else→403.
- **Single active assignment (FR-4):** partial unique index `UNIQUE(work_order_id) WHERE is_active=true`; service layer catches `IntegrityError`→409; reassign only in `assigned` state→422 if `in_progress`.
- **Completion guard (FR-6):** `completion_notes` non-empty required on `→completed`→422 if blank; parts list persisted atomically; parts+notes immutable post-completion except `dispatcher_addendum`.
- **SLA breach (FR-7, NFR-8):** board endpoint computes `sla_breached = priority=='urgent' AND scheduled_date<=today AND status NOT IN('completed','cancelled') AND now()>=17:00 SLA_TZ`; flag in response; Streamlit renders red badge on breached cards.
- **Audit log (FR-9, NFR-9):** every status transition appends to `audit_log` inside same DB transaction; no DELETE/PATCH endpoints on audit_log→405; accessible dispatcher+owner only.
- **No PII in logs (NFR-4, NFR-7):** structured JSON logger middleware records method/path/status/duration_ms/actor_role; customer fields excluded from all log lines.

## 6. DB delivery
1. Migration order: `001_create_customers.sql`, `002_create_technicians.sql`, `003_create_users.sql`, `004_create_work_orders.sql`, `005_create_assignments.sql`, `006_create_part_line_items.sql`, `007_create_audit_log.sql`
2. Seed (`seed.py`): 5 technicians (varied skills), 5 customers, 15 work orders across all statuses (mix urgent/routine, ≥1 urgent past-date not completed for SLA breach, ≥2 completed with parts+notes), assignments across ≥3 technicians, 3 users (one per role; dispatcher's technician_id=NULL, technician user linked to a seeded technician).
