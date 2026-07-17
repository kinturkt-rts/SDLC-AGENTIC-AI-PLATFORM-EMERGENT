# Team Expense Tracker — Solution Design

## 1. Summary
Internal REST API for logging, approving, and reporting on employee business expenses. Primary DB: PostgreSQL (single RDS instance). API style: FastAPI REST, versioned at `/api/v1/`. Auth via Bearer tokens (employees) and `X-Api-Key` headers (manager/admin); no JWT, no UI beyond OpenAPI `/docs`.
TBD: FX rate load mechanism, manager key team-scoping cardinality, rejection `reason` field requirement.
Diagram: `docs/generated-diagrams/expense-tracker.png`

## 2. Stack
| Layer | Technology | Path |
|-------|------------|------|
| API | FastAPI | `target-apps/expense-tracker/app/` |
| Auth | Custom header dependency (PyJWT not used) | `app/dependencies/auth.py` |
| ORM | SQLAlchemy 2.x + Alembic | `app/models/`, `alembic/` |
| DB | PostgreSQL — all money as `NUMERIC(19,4)` | Single RDS instance |
| Testing | pytest + httpx + pytest-cov | `tests/` |

## 3. Data model
| Table | Columns | Indexes / Constraints |
|-------|---------|-----------------------|
| `teams` | `id SERIAL PK`, `name VARCHAR(120) UNIQUE NOT NULL`, `created_at TIMESTAMPTZ`, `deleted_at TIMESTAMPTZ` | idx on `name` |
| `employees` | `id SERIAL PK`, `name VARCHAR(200) NOT NULL`, `team_id INT FK(teams.id)`, `token_hash VARCHAR(256) UNIQUE NOT NULL`, `role VARCHAR(20) NOT NULL DEFAULT 'employee'`, `created_at TIMESTAMPTZ` | idx on `token_hash` |
| `api_keys` | `id SERIAL PK`, `key_hash VARCHAR(256) UNIQUE NOT NULL`, `role VARCHAR(20) NOT NULL`, `owner_label VARCHAR(200)`, `team_ids INT[]`, `created_at TIMESTAMPTZ`, `revoked_at TIMESTAMPTZ` | idx on `key_hash` |
| `fx_rate_snapshots` | `currency CHAR(3) PK`, `rate_date DATE PK`, `usd_rate NUMERIC(19,6) NOT NULL`, `loaded_at TIMESTAMPTZ` | composite PK `(currency, rate_date)` |
| `expenses` | `id SERIAL PK`, `employee_id INT FK(employees.id) NOT NULL`, `team_id INT FK(teams.id) NOT NULL`, `original_amount NUMERIC(19,4) NOT NULL`, `currency CHAR(3) NOT NULL`, `usd_amount NUMERIC(19,4) NOT NULL`, `category VARCHAR(20) NOT NULL`, `description VARCHAR(500)`, `expense_date DATE NOT NULL`, `status VARCHAR(20) NOT NULL DEFAULT 'submitted'`, `created_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ`, `deleted_at TIMESTAMPTZ` | idx on `(team_id, status, expense_date)`, idx on `employee_id` |
| `audit_log` | `id SERIAL PK`, `expense_id INT FK(expenses.id) NOT NULL`, `from_status VARCHAR(20)`, `to_status VARCHAR(20) NOT NULL`, `actor_id INT NOT NULL`, `actor_role VARCHAR(20) NOT NULL`, `occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()` | idx on `expense_id`; no UPDATE/DELETE permitted |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | `/api/v1/expenses` | `{amount, currency, category, description, expense_date}` | `201 ExpenseOut` | FR-1, FR-2, FR-9; employee only |
| PATCH | `/api/v1/expenses/{id}` | `{amount?, currency?, category?, description?, expense_date?}` | `200 ExpenseOut` | FR-3; submitted only; recomputes usd_amount |
| DELETE | `/api/v1/expenses/{id}` | — | `204` | FR-8; submitted + owner only; sets deleted_at |
| GET | `/api/v1/expenses` | `?status&category&year&month&limit&offset` | `200 PagedExpenses` | FR-10; own expenses only |
| GET | `/api/v1/expenses/{id}` | — | `200 ExpenseOut` | owner or admin |
| GET | `/api/v1/expenses/{id}/audit-log` | — | `200 list[AuditEntry]` | FR-5; authorized actor |
| POST | `/api/v1/expenses/{id}/approve` | — | `200 ExpenseOut` | FR-4; admin only; 409 if non-submitted |
| POST | `/api/v1/expenses/{id}/reject` | — | `200 ExpenseOut` | FR-4; admin only; 409 if non-submitted |
| POST | `/api/v1/teams` | `{name}` | `201 TeamOut` | FR-7; admin only |
| GET | `/api/v1/teams` | — | `200 list[TeamOut]` | FR-7; admin only |
| PUT | `/api/v1/employees/{id}/team` | `{team_id}` | `200 EmployeeOut` | FR-7; admin only |
| GET | `/api/v1/teams/{team_id}/report` | `?year&month` | `200 ReportOut` | FR-6; manager scoped to team |
| GET | `/api/v1/health` | — | `200 {status, db}` | NFR-5 |

## 5. Rules
- **Auth (NFR-3)**: All routes require valid credential; `Depends(get_current_actor)` in `app/dependencies/auth.py` resolves Bearer token → employee row or `X-Api-Key` → api_keys row; missing/invalid → 401.
- **RBAC (NFR-4, FR-4, FR-7)**: `require_role(*roles)` dependency gates routes; employee routes check `actor.id == expense.employee_id`; manager routes verify `team_id in actor.team_ids`; admin has full scope; wrong role → 403.
- **Decimal integrity (NFR-2)**: All money fields typed `NUMERIC(19,4)` in DB; Pydantic models use `Decimal`; validators reject `float`; `usd_amount = ROUND(original_amount * usd_rate, 4)` computed at service layer using Python `Decimal`.
- **FX lock-in + currency validation (FR-2, FR-9)**: On submit/edit, service queries `fx_rate_snapshots(currency, expense_date)`; missing row → 422; `usd_amount` written once and never updated by fx changes.
- **Status immutability (FR-3, FR-4, FR-8)**: Status machine: `submitted → approved | rejected`; PATCH/DELETE on non-submitted → 409; approve/reject on non-submitted → 409; enforced in service layer with `SELECT FOR UPDATE`.
- **Audit log (FR-5, NFR-8)**: Every status transition (including creation) appended to `audit_log` within the same DB transaction; no UPDATE/DELETE on `audit_log` rows enforced via revoke in DB grants.
- **Soft delete only (NFR-8, FR-8)**: `DELETE /expenses/{id}` sets `deleted_at`; all list queries add `WHERE deleted_at IS NULL`; approved/rejected expenses return 409 on delete attempt.
- **Structured logging (NFR-7)**: FastAPI middleware emits JSON log per request: `request_id`, `method`, `path`, `status_code`, `latency_ms`, `actor_id`, `actor_role` to stdout.

## 6. DB delivery
1. Migration order: `001_create_teams.sql`, `002_create_employees.sql`, `003_create_api_keys.sql`, `004_create_fx_rate_snapshots.sql`, `005_create_expenses.sql`, `006_create_audit_log.sql`, `007_create_indexes.sql`
2. Seed data: 2 teams (`Engineering`, `Finance`); 3 employees (1 per role + 1 employee); 2 api_keys (1 manager, 1 admin); fx_rate_snapshots for `EUR`, `GBP`, `CAD` for current month dates; 3 sample expenses in mixed statuses.
3. Athena / NoSQL: not used.
