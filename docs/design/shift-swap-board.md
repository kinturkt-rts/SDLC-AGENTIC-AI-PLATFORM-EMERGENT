# Shift Swap Board — Solution Design

## 1. Summary
Internal staff tool for posting, claiming, and approving shift swaps with atomic roster updates and an append-only audit log. Postgres is the primary store; FastAPI serves REST endpoints; Streamlit is the sole client. Auth uses HS256 JWT (no external provider).
TBD: JWT expiry duration (assumed 8 h via `JWT_EXPIRY_HOURS`); audit log retention period; monitoring toolchain for `/health` probe.
Diagram: `docs/diagrams/generated-diagrams/shift-swap-board.png`

## 2. Stack
| Layer | Technology | Notes |
|-------|------------|-------|
| UI | Streamlit | `ui/streamlit_app.py` calls FastAPI over HTTP (port 8501) |
| API | FastAPI | `target-apps/shift-swap-board/app/`; port 8000 |
| Auth | PyJWT (HS256) + passlib bcrypt | `JWT_SECRET_KEY` from env; bcrypt cost ≥ 12 |
| ORM | SQLAlchemy 2.x sync + psycopg[binary] | `search_path=shift_swap_board` |
| DB | PostgreSQL (RDS or local Docker) | Schema `shift_swap_board` |
| Config | `.env` / `app/startup_checks.py` | Fails fast if `DATABASE_URL` or `JWT_SECRET_KEY` absent |

## 3. Data model
| Table | Columns | Indexes / constraints |
|-------|---------|-----------------------|
| `users` | `id uuid PK`, `username varchar(64) UNIQUE`, `password_hash text`, `role enum('staff','floor_lead','admin')`, `display_name varchar(128)`, `is_active bool DEFAULT true`, `created_at timestamptz` | idx on `username` |
| `staff_profiles` | `id uuid PK`, `user_id uuid FK→users UNIQUE`, `employee_code varchar(32) UNIQUE nullable` | — |
| `shift_roster` | `id uuid PK`, `staff_id uuid FK→staff_profiles`, `shift_date date`, `shift_window enum('morning','afternoon','full')`, `created_at timestamptz` | `UNIQUE(staff_id, shift_date, shift_window)`; idx on `shift_date` |
| `floor_lead_weeks` | `id uuid PK`, `week_start date`, `floor_lead_user_id uuid FK→users` | `UNIQUE(week_start)` |
| `swap_requests` | `id uuid PK`, `offered_shift_id uuid FK→shift_roster`, `offered_by_user_id uuid FK→users`, `status enum('open','claimed','approved','denied','cancelled')`, `claimed_by_user_id uuid nullable FK→users`, `claimed_at timestamptz nullable`, `decided_by_user_id uuid nullable FK→users`, `decided_at timestamptz nullable`, `decision_note text nullable`, `created_at timestamptz`, `updated_at timestamptz` | idx on `status` |
| `swap_audit_log` | `id uuid PK`, `swap_request_id uuid FK→swap_requests`, `action varchar(64)`, `actor_user_id uuid FK→users`, `detail jsonb nullable`, `created_at timestamptz DEFAULT now()` | idx on `(swap_request_id, created_at)` |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | `/auth/login` | `{username, password}` | `{access_token, token_type}` | FR-1; public |
| GET | `/health` | — | `{status}` | FR-13; public; 503 if DB down |
| GET | `/roster` | `?from=date&to=date` | `[{id, staff_id, display_name, shift_date, shift_window}]` | FR-2; all roles |
| GET | `/roster/mine` | — | same row shape | FR-2; staff/floor_lead |
| GET | `/swaps` | `?status=&week_start=` | `[SwapRequest]` | FR-8; filtered by role |
| POST | `/swaps` | `{offered_shift_id}` | `SwapRequest` 201 | FR-3; staff only |
| POST | `/swaps/{id}/claim` | — | `SwapRequest` | FR-4; staff only; 403/409/422 |
| POST | `/swaps/{id}/approve` | `{decision_note?}` | `SwapRequest` | FR-5; floor_lead, same week |
| POST | `/swaps/{id}/deny` | `{decision_note?}` | `SwapRequest` | FR-6; floor_lead, same week |
| POST | `/swaps/{id}/cancel` | — | `SwapRequest` | FR-7; offerer only |
| GET | `/swaps/{id}/audit` | — | `[AuditRow]` | FR-9; admin or floor_lead |
| GET | `/audit` | `?limit=int` | `[AuditRow]` | FR-9; admin only; default limit 50 |
| GET | `/floor-leads` | — | `[FloorLeadWeek]` | FR-10; admin |
| POST | `/floor-leads` | `{week_start, floor_lead_user_id}` | `FloorLeadWeek` 201 | FR-10; admin; 409 dup week, 422 wrong role |

## 5. Rules
- **Auth**: Bearer JWT required on all routes except `/auth/login` and `/health`; missing/expired → 401 (FR-1, NFR-1).
- **RBAC**: `staff` — create/claim/cancel swaps, read own roster; `floor_lead` — approve/deny for assigned week only, read claimed swaps for that week + audit; `admin` — floor-lead mgmt, full audit, all reads (NFR-2).
- **Week guard**: `/swaps/{id}/approve` and `/swaps/{id}/deny` verify caller's `user_id` matches `floor_lead_weeks.floor_lead_user_id` for the ISO week of `offered_shift.shift_date`; else 403 (FR-5, FR-6).
- **Overlap guard**: application-layer check `UNIQUE(staff_id, shift_date, shift_window)` before any DB write → 422 with human-readable detail; DB unique index is secondary safety net (FR-11).
- **Atomic approve**: single SQLAlchemy transaction — delete offerer's `shift_roster` row, insert accepter's row, set `status='approved'`, append `approved` + `roster_updated` audit rows; rollback on any error (FR-5, NFR-5).
- **Audit immutability**: no `DELETE` or `UPDATE` on `swap_audit_log` anywhere in application code; no `ON DELETE CASCADE` from `swap_requests` to audit (NFR-6, NFR-8).
- **Status transitions**: `open→claimed`, `open→cancelled`, `claimed→approved`, `claimed→denied`, `claimed→cancelled`; terminal states (`approved`, `denied`, `cancelled`) reject further transitions with 409.
- **`week_start` validation**: `POST /floor-leads` returns 422 if supplied date is not a Monday.

## 6. DB delivery
1. Migration order: `001_create_enum_types.sql`, `002_users.sql`, `003_staff_profiles.sql`, `004_shift_roster.sql`, `005_floor_lead_weeks.sql`, `006_swap_requests.sql`, `007_swap_audit_log.sql`
2. Seed (`seeds/seed.py`): 1 admin (`admin`), 2 floor_leads (`lead_a`, `lead_b`), 6 staff (`staff_01`…`staff_06`); all passwords bcrypt hash (cost 12) of `"Password1!"`; `floor_lead_weeks` for current + next Monday; ~12 `shift_roster` rows across next 7 days (mix of morning/afternoon/full); 3 `swap_requests` (1 `open`, 1 `claimed`, 1 `approved`) with corresponding `swap_audit_log` rows; `verify_seed_bcrypt` step asserts no plaintext hashes (FR-14, NFR-1).
