# Contact Directory API — Solution Design

## 1. Summary
Internal REST API for colleague contact information with department organization. Postgres backend with tiered access: anonymous reads, API key-protected writes. Validates Pattern B SDLC architecture.

## 2. Stack
| Layer | Technology |
|-------|------------|
| API | FastAPI + Uvicorn |
| Database | PostgreSQL 15+ |
| Auth | API key headers |
| Docs | OpenAPI/Swagger |
| Config | Python-dotenv |

## 3. Data model
| Table / collection | Columns (name type PK/FK UNIQUE) | Indexes / constraints |
|--------------------|----------------------------------|------------------------|
| departments | id uuid PK, name text NOT NULL, code text UNIQUE NOT NULL, created_at timestamp | UNIQUE(code), CHECK(length(name) 1-80), CHECK(code ~* '^[A-Z]{2,10}$') |
| contacts | id uuid PK, department_id uuid FK, full_name text NOT NULL, email text UNIQUE, phone text, title text, is_active boolean DEFAULT true, created_at timestamp, updated_at timestamp | UNIQUE(email), FK(department_id→departments.id), CHECK(length(full_name) 1-120), CHECK(length(phone) ≤30), CHECK(length(title) ≤80) |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | /health | - | `{"status": "ok", "service": "contacts-api"}` | No auth |
| GET | /contacts | `?limit=50&offset=0&q=search` | `{"items": [ContactRead], "total": int, "limit": int, "offset": int}` | No auth |
| GET | /contacts/{id} | - | `ContactRead` | No auth |
| POST | /contacts | `ContactCreate` | `ContactRead` | API key required |
| PATCH | /contacts/{id} | `ContactUpdate` | `ContactRead` | API key required |
| DELETE | /contacts/{id} | - | 204 | API key required, soft delete |
| GET | /departments | - | `[DepartmentRead]` | No auth |
| POST | /departments | `DepartmentCreate` | `DepartmentRead` | API key required |
| PATCH | /departments/{id} | `DepartmentUpdate` | `DepartmentRead` | API key required |

## 5. Rules
- Auth: Single shared API key via `X-API-Key` header for all write operations (POST/PATCH/DELETE)
- Anonymous access: All GET endpoints accessible without authentication
- Search: Case-insensitive partial matching on `full_name` and `email` fields via `?q=` parameter
- Soft delete: DELETE sets `is_active=false`, preserves records for audit
- Validation: Email uniqueness constraint, department_id foreign key validation
- Error handling: 401 for auth failures, 404 for missing resources, 409 for conflicts
- Pagination: Default limit=50, max=100 for contact listings
- Audit: Log all write operations with timestamp and operation type

## 6. DB delivery
1. Migration order: `001_create_departments.sql`, `002_create_contacts.sql`, `003_add_indexes.sql`
2. Seed data: Sample departments (ENG, SALES, MKTG), 5-10 test contacts per department
3. Environment: `DATABASE_URL`, `API_KEY` configuration via .env
