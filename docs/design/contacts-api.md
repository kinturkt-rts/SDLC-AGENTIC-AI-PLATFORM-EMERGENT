# contacts-api — Solution Design

## 1. Summary
A FastAPI REST service for an internal contact directory backed by PostgreSQL (schema `contacts_api`). Write endpoints are guarded by a single shared `X-API-Key`; all reads are public. Deployed via uvicorn; SQLite in-memory for unit tests.
TBD: Postgres target version (14/15/16), default/max page size, health liveness-vs-readiness split.
`Diagram: docs/diagrams/generated-diagrams/contacts-api.png`

## 2. Stack
| Layer | Technology |
|-------|------------|
| API | FastAPI 0.111+ / Python 3.12 |
| ORM | SQLAlchemy 2.x (async-optional) |
| DB | PostgreSQL — schema `contacts_api` |
| Test DB | SQLite in-memory (dialect guard) |
| Validation | Pydantic v2 (`EmailStr`) |
| Server | Uvicorn (`PORT` env, default 8000) |

## 3. Data model
| Table | Columns (name type PK/FK UNIQUE) | Indexes / constraints |
|-------|----------------------------------|-----------------------|
| `departments` | `id uuid PK`, `name text NOT NULL`, `code text UNIQUE NOT NULL`, `created_at timestamptz NOT NULL DEFAULT now()` | `UNIQUE(code)`; code 2–10 uppercase chars |
| `contacts` | `id uuid PK`, `department_id uuid FK→departments.id`, `full_name text NOT NULL`, `email text UNIQUE NOT NULL`, `phone text`, `title text`, `is_active bool NOT NULL DEFAULT true`, `created_at timestamptz NOT NULL DEFAULT now()`, `updated_at timestamptz NOT NULL DEFAULT now()` | `idx_contacts_email`, `idx_contacts_department_id`, `idx_contacts_is_active`; FK ON DELETE RESTRICT |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | `/health` | — | `{"status":"ok","service":"contacts-api"}` 200 | FR-1; no auth |
| POST | `/departments` | `{name:str, code:str}` | `DepartmentOut` 201 | FR-3; 409 on dup code |
| GET | `/departments` | — | `list[DepartmentOut]` 200 | FR-4; sorted by name |
| GET | `/departments/{id}` | — | `DepartmentOut+contact_count:int` 200/404 | FR-4 |
| PATCH | `/departments/{id}` | `{name?:str, code?:str}` | `DepartmentOut` 200 | FR-5; 409 dup code |
| POST | `/contacts` | `{full_name:str, email:EmailStr, department_id:UUID, phone?:str, title?:str}` | `ContactOut` 201 | FR-6; 404 bad dept, 409 dup email |
| GET | `/contacts` | `?q=&department_id=&is_active=&limit=&offset=` | `{items,total,limit,offset}` 200 | FR-7; default limit 20, max 100 |
| GET | `/contacts/{id}` | — | `ContactOut` 200/404 | FR-8 |
| PATCH | `/contacts/{id}` | `{full_name?:str, email?:EmailStr, phone?:str, title?:str, department_id?:UUID}` | `ContactOut` 200 | FR-9; bumps `updated_at` |
| DELETE | `/contacts/{id}` | — | 204 | FR-10; sets `is_active=false` |

## 5. Rules
- **Auth**: `verify_api_key` FastAPI dependency reads `X-API-Key` header; constant-time compare vs `settings.API_KEY`; applied to all `POST`, `PATCH`, `DELETE` routes only (NFR-1).
- **401 shape**: `{"detail":"Invalid or missing API key"}` on missing or wrong key (FR-2).
- **No key in logs**: structured JSON logs emit method/path/status/duration; `API_KEY` value never logged (NFR-1, NFR-2).
- **Soft-delete only**: `DELETE /contacts/{id}` flips `is_active=false`; no hard deletes anywhere (FR-10, NFR-8).
- **Email uniqueness**: duplicate email across active *and* inactive contacts → 409 (FR-6, FR-9).
- **`updated_at` bump**: SQLAlchemy `onupdate=func.now()` on `contacts.updated_at`; no caller-supplied timestamp (Appendix assumption).
- **Pagination**: `limit` default 20, max 100; `total` reflects filtered count (FR-7, Appendix).
- **Observability**: global exception handler logs ERROR with route/method/status; startup logs `PORT` and schema name, never key (NFR-6).

## 6. DB delivery
1. Migration order:
   - `001_create_schema.sql` — `CREATE SCHEMA IF NOT EXISTS contacts_api`
   - `002_create_departments.sql` — departments DDL + indexes
   - `003_create_contacts.sql` — contacts DDL + FK + indexes
   - `004_seed.sql` — 3 departments + 6–8 contacts (stable UUIDs, `ON CONFLICT DO NOTHING`)
2. Seed data (stable UUIDs):
   - Departments: Engineering/ENG, Sales/SALES, HR/HR
   - Contacts: 6 active + 1 `is_active=false`; all reference one of the three seed departments
3. DDL path: `target-apps/contacts-api/db/sql/`; `HANDOFF.md` lists migration order, seed UUIDs, and `search_path=contacts_api` setup note.
