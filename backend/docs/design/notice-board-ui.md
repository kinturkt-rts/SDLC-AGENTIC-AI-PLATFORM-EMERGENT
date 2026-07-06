# Team Notice Board — Solution Design

## 1. Summary
Web-based notice board for company announcements with Streamlit UI and FastAPI backend. Organizers manage notices with shared secret auth; employees browse active announcements. PostgreSQL stores notices and categories with scheduling and archival support.
Diagram: C:/Users/KinturShah/OneDrive - Resolve Tech Solutions/KT - Personal/SDLC Agentic AI Platform/docs/generated-diagrams/notice-board-ui.png

## 2. Stack
| Layer | Technology | Location |
|-------|------------|----------|
| UI | Streamlit | ui/streamlit_app.py calls FastAPI over HTTP (port 8501) |
| API | FastAPI | target-apps/notice-board-ui/ REST + OpenAPI |
| Database | PostgreSQL | RDS with connection pooling |
| Cache | Redis | ElastiCache for session management |
| Load Balancer | ALB | Traffic distribution to EC2 instances |

## 3. Data model
| Table | Columns (name type PK/FK UNIQUE) | Indexes / constraints |
|-------|----------------------------------|------------------------|
| categories | id SERIAL PK, name VARCHAR(100) UNIQUE NOT NULL, description TEXT, created_at TIMESTAMP | idx_categories_name |
| notices | id SERIAL PK, title VARCHAR(200) NOT NULL, body TEXT NOT NULL, category_id INT FK(categories.id), author_display_name VARCHAR(100) NOT NULL, start_date DATE, end_date DATE, archived BOOLEAN DEFAULT false, created_at TIMESTAMP, updated_at TIMESTAMP | idx_notices_category, idx_notices_active, idx_notices_dates |
| audit_log | id SERIAL PK, table_name VARCHAR(50), operation VARCHAR(10), record_id INT, organizer_action BOOLEAN, created_at TIMESTAMP | idx_audit_table_record |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | /api/v1/notices | query params: category_id, search, page, limit | NoticeListResponse | Active notices only, supports filtering |
| POST | /api/v1/notices | CreateNoticeRequest + organizer_secret header | NoticeResponse | Requires organizer auth |
| PUT | /api/v1/notices/{id} | UpdateNoticeRequest + organizer_secret header | NoticeResponse | Requires organizer auth |
| DELETE | /api/v1/notices/{id}/archive | organizer_secret header | StatusResponse | Sets archived=true |
| GET | /api/v1/categories | - | CategoryListResponse | All categories for dropdowns |
| POST | /api/v1/categories | CreateCategoryRequest + organizer_secret header | CategoryResponse | Requires organizer auth |
| GET | /health | - | HealthResponse | System status check |

## 5. Rules
- Auth: Shared organizer secret in `ORGANIZER_SECRET` env var required for POST/PUT/DELETE operations
- RBAC: Two roles - anonymous readers (GET only), organizers (full CRUD with secret)
- Active notices: Only shown if archived=false AND current date between start_date/end_date (if set)
- Audit: Log all organizer operations (notice/category CRUD) with timestamps and operation type
- Search: Case-insensitive partial matching on notice title and body fields
- Pagination: Default 20 notices per page, configurable via limit parameter
- Validation: Category must exist before assigning to notice; unique category names enforced
- Archival: Notices marked archived=true preserved but hidden from browse view

## 6. DB delivery
1. Migration order: `001_create_categories.sql`, `002_create_notices.sql`, `003_create_audit_log.sql`
2. Seed data: Default categories (General, HR, IT, Events), sample archived notice for testing
3. Indexes: Composite index on (archived, start_date, end_date) for active notice queries
