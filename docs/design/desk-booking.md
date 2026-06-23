# Hot Desk Booking — Solution Design

## 1. Summary
Internal API-only tool for employees to reserve hot-desks by date and time slot (full/AM/PM) across office zones. PostgreSQL (RDS) enforces conflict prevention via multi-column UNIQUE constraints. REST API built with FastAPI; auth via opaque token headers (`X-User-Token`, `X-Admin-Key`).
`Diagram: docs/diagrams/generated-diagrams/desk-booking.png`
TBD: Token rotation strategy; partial-day blackouts; audit trail for admin actions.

## 2. Stack
| Layer | Technology | Path |
|-------|------------|------|
| API | FastAPI (Python 3.11) | `target-apps/desk-booking/` |
| Auth | Header token check (PyJWT Phase-2) | middleware validates against `users.user_token` / env `ADMIN_KEY` |
| Database | PostgreSQL 15 (RDS) | primary store for all entities |
| ORM | SQLAlchemy 2 + Alembic | `target-apps/desk-booking/db/` |
| Runtime | EC2 / container behind ALB | single-region MVP |

## 3. Data model
| Table | Columns | Indexes / Constraints |
|---|---|---|
| `zones` | `id uuid PK`, `name text UNIQUE`, `created_at timestamptz` | UNIQUE `name`; CHECK `name IN ('north','south','lab')` |
| `desks` | `id uuid PK`, `zone_id uuid FK→zones`, `label text`, `is_active bool DEFAULT true`, `created_at timestamptz` | IDX `(zone_id, is_active)` |
| `users` | `id uuid PK`, `email text UNIQUE`, `full_name text`, `user_token text UNIQUE`, `is_admin bool DEFAULT false`, `created_at timestamptz` | UNIQUE `email`, `user_token` |
| `bookings` | `id uuid PK`, `desk_id uuid FK→desks`, `user_id uuid FK→users`, `booking_date date`, `slot slot_enum NOT NULL`, `created_at timestamptz` | UNIQUE `(desk_id, booking_date, slot)`; IDX `(user_id, booking_date)`; IDX `(desk_id, booking_date)` |
| `blackouts` | `id uuid PK`, `desk_id uuid FK→desks`, `starts_on date`, `ends_on date`, `reason text`, `created_at timestamptz` | IDX `(desk_id, starts_on, ends_on)`; CHECK `ends_on >= starts_on` |

**Enum:** `slot_enum` = `'full'`, `'am'`, `'pm'`

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| `GET` | `/api/v1/health` | — | `{status}` | liveness |
| `GET` | `/api/v1/zones` | — | `[{id,name}]` | public |
| `GET` | `/api/v1/desks` | `?zone_id&is_active` | `[{id,zone_id,label,is_active}]` | public |
| `POST` | `/api/v1/desks` | `{zone_id,label}` | `{id,zone_id,label,is_active}` | admin only |
| `PATCH` | `/api/v1/desks/{id}` | `{is_active?}` | `{id,is_active}` | admin only (disable/enable) |
| `GET` | `/api/v1/availability` | `?date&zone_id` | `[{desk_id,label,zone,slot,available}]` | public; FR-6 |
| `POST` | `/api/v1/bookings` | `{desk_id,booking_date,slot}` | `{id,desk_id,user_id,booking_date,slot}` | user token; FR-1–5 |
| `GET` | `/api/v1/bookings/mine` | `?page&size` | `{items:[],total}` | user token; FR-7 |
| `DELETE` | `/api/v1/bookings/{id}` | — | `204` | owner or admin; FR-8 |
| `POST` | `/api/v1/blackouts` | `{desk_id,starts_on,ends_on,reason}` | `{id,...}` | admin only; FR-5 |

## 5. Rules
- **Auth:** `X-User-Token` header resolved to `users` row; `X-Admin-Key` matched against `ADMIN_KEY` env var. Unauthenticated → 401. Non-admin on admin route → 403.
- **Conflict – desk+date+slot (FR-1):** DB UNIQUE `(desk_id, booking_date, slot)` raises `IntegrityError` → 409 with `conflicting_booking_id`.
- **Conflict – full vs AM/PM (FR-3):** Before insert, query existing slots for `desk_id + date`; `full` blocks `am`/`pm` and vice-versa → 409.
- **One booking per user per date (FR-2):** Query `bookings WHERE user_id=? AND booking_date=?` before insert → 409.
- **Booking window (FR-4):** `booking_date` must satisfy `today ≤ date ≤ today+30`; else 422.
- **Blackout check (FR-5):** Query `blackouts WHERE desk_id=? AND starts_on ≤ date ≤ ends_on` before insert → 409 with `reason`.
- **Delete guard (FR-8):** `booking.user_id == current_user.id OR current_user.is_admin`; else 403.
- **Logging (NFR-6):** Structured JSON log every 409 with `desk_id`, `booking_date`, `slot`, `reason`.

## 6. DB delivery
1. Migration order: `001_create_enums_zones_users.sql`, `002_create_desks.sql`, `003_create_bookings.sql`, `004_create_blackouts.sql`
2. Seed data: 3 zones (`north`, `south`, `lab`); 2 desks per zone; 2 users (1 standard, 1 admin with `is_admin=true`); 1 active blackout on desk-1 for tomorrow.
3. Athena / NoSQL: not used.
