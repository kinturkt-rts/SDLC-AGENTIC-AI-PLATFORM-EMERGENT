# Team Notice Board — Solution Design

## 1. Summary
Team Notice Board API manages announcements and wins with FastAPI/Postgres backend and Streamlit dashboard. API-key auth for write operations, public read access for dashboards/bots. TBD: concurrent load expectations, rate limiting strategy.

## 2. Stack
| Layer | Technology | Notes |
|-------|------------|-------|
| UI | Streamlit | ui/streamlit_app.py calls FastAPI over HTTP (port 8501) |
| API | FastAPI | target-apps/gitlab-pipeline-smoke/ with Swagger /docs |
| Database | PostgreSQL | RDS with gitlab_pipeline_smoke schema |
| Auth | API key | X-API-Key header validation from env var |

## 3. Data model
| Table / collection | Columns (name type PK/FK UNIQUE) | Indexes / constraints |
|--------------------|----------------------------------|------------------------|
| categories | id uuid PK, name text UNIQUE, description text, created_at timestamptz | name 1-60 chars, description max 240 |
| notices | id uuid PK, category_id uuid FK, title text, body text, author_name text, starts_at timestamptz, ends_at timestamptz, is_archived boolean, created_at timestamptz, updated_at timestamptz | title 1-120 chars, body 1-4000 chars, author_name 1-80 chars, ends_at >= starts_at |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | /health | - | {"status": "ok", "service": "gitlab-pipeline-smoke"} | Public health check |
| GET | /api/v1/categories | - | List[CategoryResponse] | Public list for UI dropdowns |
| POST | /api/v1/categories | CategoryCreate | CategoryResponse | Requires X-API-Key |
| GET | /api/v1/notices | active_only?: bool, q?: str, offset?: int, limit?: int | PaginatedNoticesResponse | Public with filters |
| POST | /api/v1/notices | NoticeCreate | NoticeResponse | Requires X-API-Key |
| PATCH | /api/v1/notices/{id} | NoticeUpdate | NoticeResponse | Requires X-API-Key |
| POST | /api/v1/notices/{id}/archive | - | 204 No Content | Requires X-API-Key, idempotent |

## 5. Rules
- Auth: X-API-Key header required for POST/PATCH/archive operations, 401 for invalid/missing key
- Public access: GET /notices and GET /categories require no authentication
- Active filtering: active_only=true excludes archived, expired (ends_at < now), and future (starts_at > now) notices  
- Search: q parameter performs case-insensitive partial match on title OR body fields
- Validation: ends_at >= starts_at, category name uniqueness, field length limits per data model
- Archival: is_archived=true soft delete, idempotent archive endpoint returns 204
- Pagination: offset/limit with default limit=20, max limit=100

## 6. DB delivery
1. Migration order: `001_create_categories.sql`, `002_create_notices.sql`
2. Seed data: 3 categories (General, HR, Engineering), 5 sample notices with mixed states (active, future, expired, archived)
3. Indexes: category name unique, notice category_id FK with cascade delete restrict
