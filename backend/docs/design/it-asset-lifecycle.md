# IT Asset Lifecycle — Solution Design

## 1. Summary
Full asset lifecycle management (procurement → assignment → maintenance → retirement) for IT Ops and Finance personas. PostgreSQL via SQLAlchemy; FastAPI REST backend; Streamlit role-gated UI. Diagram: `docs/generated-diagrams/it-asset-lifecycle.png`
TBD: deployment env, key-rotation procedure, pagination on list endpoints, retention policy for `assignment_history`.

## 2. Stack
| Layer | Technology | Path |
|-------|-----------|------|
| UI | Streamlit | `ui/streamlit_app.py` calls FastAPI over HTTP (port 8501) |
| API | FastAPI + SQLAlchemy | `target-apps/it-asset-lifecycle/app/` |
| Auth | JWT HS256 + bcrypt ≥12 | `app/routers/auth.py`, `app/deps.py` |
| Encryption | Fernet (`cryptography`) | `ASSET_ENCRYPTION_KEY` env var; service layer only |
| DB | PostgreSQL (RDS) | `target-apps/it-asset-lifecycle/db/sql/` |
| Storage/Events | S3 + SQS + SNS | Reports export, lifecycle event fan-out |

## 3. Data model
| Table | Columns | Indexes / Constraints |
|-------|---------|-----------------------|
| `users` | `id uuid PK`, `username varchar UNIQUE`, `password_hash text`, `role enum(it_admin,it_staff,finance_readonly)`, `is_active bool` | unique `username` |
| `employees` | `id uuid PK`, `full_name varchar`, `email varchar UNIQUE`, `department varchar(64)`, `manager_id uuid FK→employees nullable`, `is_active bool DEFAULT true`, `deactivated_at timestamptz` | idx `(is_active)` |
| `assets` | `id uuid PK`, `asset_type enum(laptop,monitor,phone,license,misc)`, `manufacturer varchar`, `model varchar`, `serial_number varchar UNIQUE nullable`, `license_key_encrypted text nullable`, `license_key_last4 varchar(4)`, `seats_purchased int nullable`, `purchase_date date`, `purchase_cost numeric(12,2)`, `warranty_end_date date nullable`, `status enum(in_stock,assigned,repair,retired)`, `created_at timestamptz`, `updated_at timestamptz` | idx `(warranty_end_date, status)`, idx `(asset_type)`, idx `(status)` |
| `assignments` | `id uuid PK`, `asset_id uuid FK→assets`, `employee_id uuid FK→employees`, `assigned_at timestamptz`, `returned_at timestamptz nullable`, `assigned_by uuid FK→users`, `return_condition_note text nullable` | partial UNIQUE `(asset_id) WHERE returned_at IS NULL`; enforces FR-2 |
| `assignment_history` | `id uuid PK`, `asset_id uuid FK→assets`, `employee_id uuid FK→employees`, `event_type enum(assign,return)`, `event_at timestamptz`, `actor_id uuid FK→users`, `condition_note text nullable` | append-only; no UPDATE/DELETE via API (NFR-10) |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | `/auth/login` | `{username, password}` | `{access_token, role}` | FR-10; no auth required |
| GET | `/health` | — | `{status, db}` | NFR-9; anonymous |
| GET | `/assets` | `?type&status&warranty_expiring_within_days` | `AssetOut[]` | FR-1, FR-11; `license_key_last4` only |
| POST | `/assets` | `AssetCreate` | `AssetOut 201` | FR-1; `it_admin` only |
| PATCH | `/assets/{id}` | `AssetUpdate` | `AssetOut` | FR-1; `it_admin` only |
| POST | `/assets/{id}/assign` | `{employee_id}` | `AssignmentOut 201` | FR-2, FR-3, FR-4; `it_admin`,`it_staff`; serialisable tx + SELECT FOR UPDATE |
| POST | `/assets/{id}/return` | `{condition: enum(in_stock,repair), note?}` | `AssignmentOut` | FR-4; `it_admin`,`it_staff` |
| POST | `/assets/{id}/retire` | — | `AssetOut` | FR-5; `it_admin` only |
| PATCH | `/employees/{id}/deactivate` | — | `EmployeeOut` | FR-6; `it_admin` only |
| GET | `/alerts/offboarding` | — | `OffboardingAlert[]` | FR-7; `it_admin`,`it_staff` |
| GET | `/alerts/warranty` | `?days=30` | `AssetOut[]` | FR-7; all auth roles |
| GET | `/alerts/license-overages` | — | `LicenseOverageAlert[]` | FR-7; `it_admin`,`it_staff` |
| GET | `/reports/valuation-by-department` | — | `{department,total_cost,asset_count}[]` | FR-9; `it_admin`,`finance_readonly` |

## 5. Rules
- **RBAC:** `it_admin` — all endpoints; `it_staff` — GET assets/employees, assign, return, alerts; `finance_readonly` — GET-only + valuation report, 403 on all write endpoints (FR-8).
- **JWT:** HS256, `JWT_SECRET` env var, TTL from `JWT_TTL_HOURS` (default 8 h); 401 on missing/expired token (FR-10, NFR-4).
- **License key masking:** Serialisation layer (`AssetOut`) always emits `license_key_last4`; `license_key_encrypted` never in any response (FR-8, NFR-5).
- **Seat-check transaction:** `POST /assets/{id}/assign` uses `SELECT FOR UPDATE` on active assignment count inside a serialisable transaction; 422 `{"detail":"no seats available"}` or `{"detail":"asset already assigned"}` on violation (FR-2, FR-3, NFR-2).
- **Retire guard:** 422 if `status=assigned` or any active assignment exists (FR-5).
- **Audit log:** Every assign/return appends an immutable row to `assignment_history`; no API route exposes UPDATE/DELETE on this table (FR-12, NFR-10).
- **Fernet:** Encrypt on write, decrypt in service layer only; app fails fast if `ASSET_ENCRYPTION_KEY` absent (NFR-3).
- **Passwords:** bcrypt cost ≥ 12; plaintext never logged (NFR-12).

## 6. DB delivery
1. Migration order: `001_create_users.sql`, `002_create_employees.sql`, `003_create_assets.sql`, `004_create_assignments.sql`, `005_create_assignment_history.sql`, `006_create_indexes.sql`
2. Seed (`db/sql/seed.sql`, idempotent via `ON CONFLICT DO NOTHING`): 4 users (one per role + spare `it_staff`), 12 employees (2 `is_active=false` each with ≥1 active assignment), 25 assets (5 license with defined `seats_purchased`, synthetic serial/license values), ≥20 `assignment_history` rows.
3. Athena/NoSQL: not used in MVP.
