# Expense Tracker — Solution Design

## 1. Summary
Internal REST API for employee expense submission, admin approval/rejection, and manager team-spend reporting with at-submit-time FX conversion. PostgreSQL stores all monetary values as `NUMERIC(19,4)`; API keys + employee tokens authenticate all requests. Streamlit UI wraps the FastAPI service for interactive use.
Diagram: `docs/generated-diagrams/expense-tracker.png`
TBD: supported currency list, manager key team-scope, employee token issuance mechanism, retention policy.

## 2. Stack
| Layer | Technology | Path / Notes |
|-------|------------|--------------|
| API | FastAPI + Python 3.12 | `target-apps/expense-tracker/app/` |
| UI | Streamlit | `ui/streamlit_app.py` calls FastAPI over HTTP (port 8501) |
| ORM | SQLAlchemy (async) + asyncpg | `app/models/` |
| DB | PostgreSQL (RDS / local) | NUMERIC(19,4); Alembic migrations |
| Auth | API key + employee token (hashed, bcrypt) | FastAPI `Depends(require_role)` |
| Config | `.env` via `pydantic-settings` | No Cognito, no JWT |

## 3. Data model
| Table | Columns | Indexes / Constraints |
|-------|---------|-----------------------|
| `teams` | `id UUID PK`, `name VARCHAR(255) UNIQUE`, `description TEXT`, `created_at TIMESTAMPTZ`, `deleted_at TIMESTAMPTZ` | — |
| `users` | `id UUID PK`, `email VARCHAR(255) UNIQUE`, `role VARCHAR(20)`, `team_id UUID FK→teams`, `token_hash TEXT`, `created_at TIMESTAMPTZ`, `deleted_at TIMESTAMPTZ` | `idx_users_team(team_id)` |
| `api_keys` | `id UUID PK`, `key_hash TEXT`, `role VARCHAR(20)`, `description TEXT`, `created_at TIMESTAMPTZ`, `revoked_at TIMESTAMPTZ` | — |
| `fx_snapshots` | `id UUID PK`, `currency CHAR(3)`, `date DATE`, `rate_to_usd NUMERIC(19,4)` | `UNIQUE(currency, date)` |
| `expenses` | `id UUID PK`, `user_id UUID FK→users`, `team_id UUID FK→teams`, `amount NUMERIC(19,4)`, `currency CHAR(3)`, `amount_usd NUMERIC(19,4)`, `category VARCHAR(20)`, `description VARCHAR(1000)`, `expense_date DATE`, `status VARCHAR(20) DEFAULT 'submitted'`, `reason TEXT`, `created_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ`, `deleted_at TIMESTAMPTZ` | `idx_expenses_team_date(team_id, expense_date, status, deleted_at)`, `idx_expenses_user(user_id, status)` |
| `audit_log` | `id UUID PK`, `expense_id UUID FK→expenses`, `actor_id UUID`, `actor_role VARCHAR(20)`, `action VARCHAR(30)`, `from_status VARCHAR(20)`, `to_status VARCHAR(20)`, `metadata JSONB`, `created_at TIMESTAMPTZ` | `idx_audit_expense(expense_id, created_at)` |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | `/health` | — | `{status, db}` | Unauthenticated |
| POST | `/api/v1/expenses` | `{amount:Decimal, currency, category, description, expense_date}` | `201 ExpenseOut` | FR-1; employee only; FX lookup → 422 if missing |
| PATCH | `/api/v1/expenses/{id}` | `{amount?, currency?, category?, description?, expense_date?}` | `200 ExpenseOut` | FR-3; owner only; 409 if approved/rejected |
| DELETE | `/api/v1/expenses/{id}` | — | `204` | FR-4; owner only; 409 if not submitted |
| GET | `/api/v1/expenses/{id}` | — | `200 ExpenseOut` | Owner or admin |
| GET | `/api/v1/expenses` | `?status&page&size` | `200 List[ExpenseOut]` | Employee sees own; admin sees all |
| POST | `/api/v1/expenses/{id}/approve` | `{reason?:str}` | `200 ExpenseOut` | FR-5; admin only |
| POST | `/api/v1/expenses/{id}/reject` | `{reason?:str}` | `200 ExpenseOut` | FR-5; admin only |
| GET | `/api/v1/expenses/{id}/audit` | — | `200 List[AuditEntry]` | FR-8; admin only |
| POST | `/api/v1/teams` | `{name:str, description?:str}` | `201 TeamOut` | FR-7; admin only |
| GET | `/api/v1/teams` | — | `200 List[TeamOut]` | Admin/manager |
| PATCH | `/api/v1/teams/{team_id}/members` | `{user_id:UUID, action:assign\|remove}` | `200 UserOut` | FR-7; admin only |
| GET | `/api/v1/teams/{team_id}/expenses/summary` | `?year=YYYY&month=MM` | `200 SummaryOut` | FR-6; manager only |
| POST | `/api/v1/fx-snapshots` | `{currency, date, rate_to_usd:Decimal}` | `201 FXSnapshotOut` | FR-10; admin only |

## 5. Rules
- **Auth / API key (NFR-1, NFR-2, FR-9):** All endpoints (except `/health`) require `X-API-Key` header; FastAPI `Depends(require_role("employee"|"manager"|"admin"))` validates hash against `users.token_hash` or `api_keys.key_hash` (bcrypt); missing key → 401; wrong role → 403. Streamlit: `st.session_state.api_key` gate on all pages; sidebar login form when absent.
- **RBAC scopes (FR-9, NFR-2):** employee=own CRUD only; manager=GET teams/summary only; admin=approve/reject/teams/audit/fx. Streamlit: employee tab=Submit+My Expenses; manager tab=Team Summary; admin tab=Approve/Reject+Teams+Audit.
- **FX lookup at submit/edit (FR-1, FR-3, FR-10):** `app/services/fx.py` queries `fx_snapshots(currency, expense_date)`; raises `FXRateNotFound` → HTTP 422 `{"detail":"No FX rate available for <X> on <D>"}`. Frozen on row at write; never recomputed on read (FR-2).
- **Immutability of finalised expenses (FR-5, NFR-8):** `app/services/expenses.py` checks `status in (approved, rejected)` before any mutation; returns 409. `SELECT FOR UPDATE` during approve/reject transition prevents race conditions.
- **Soft-delete only (FR-4, NFR-8):** `deleted_at` timestamp set; hard DELETE on `expenses`/`audit_log` forbidden; DB app-user has no DELETE privilege. All list/aggregate queries filter `deleted_at IS NULL`.
- **Audit trail (FR-8, NFR-7):** `app/services/audit.py` inserts to `audit_log` on every create/update/status-change/soft-delete; append-only (no UPDATE/DELETE permitted on table); every status transition → 100% log coverage.
- **Decimal precision (NFR-3):** All monetary Pydantic fields typed `Decimal`; serialised as strings in JSON; lint rule bans `float` for money; DB columns `NUMERIC(19,4)`; API responses round `amount_usd` to 2 dp.
- **Aggregation performance (FR-6, NFR-4):** Monthly summary queries use composite index `(team_id, expense_date, status, deleted_at)`; approved + non-deleted filter only; P95 target ≤ 500 ms.

## 6. DB delivery
1. Migration order: `001_create_teams.sql`, `002_create_users.sql`, `003_create_api_keys.sql`, `004_create_fx_snapshots.sql`, `005_create_expenses.sql`, `006_create_audit_log.sql`, `007_create_indexes.sql`
2. Seed data: 1 admin api_key row (bcrypt hash of `ADMIN_KEY_DEV`); 1 manager api_key row; 2 employee users in 1 team; FX snapshot rows for USD/GBP/EUR on current date (rate 1.0 / 1.27 / 1.09)
3. Alembic: each migration includes `upgrade()` and `downgrade()`; no Athena/NoSQL used.
