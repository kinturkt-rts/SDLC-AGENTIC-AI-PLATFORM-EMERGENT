# Team Notice Board — Shared Announcements with Browser UI

## 1. Overview

Morgan runs internal comms for a mid-size company and faces the problem of important updates disappearing in Slack within a day. The Team Notice Board provides a persistent web-based solution where organizers can post and manage company announcements while employees can easily browse active notices without requiring developer tools or API knowledge.

The system consists of a FastAPI backend serving notices and categories, with a Streamlit web interface for both browsing (all users) and management (organizers with shared secret). Notices support categorization, scheduling with publish windows, and archiving for historical record-keeping.

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Replace ephemeral Slack announcements | Weekly active notices posted | 10+ per week | Consistent communication flow |
| Enable non-developer organizer access | Organizers using web UI vs API | 100% web UI adoption | No Swagger dependency for content management |
| Improve notice discoverability | Employee engagement with browsing | 80% of employees browse weekly | Persistent, searchable content |
| Reduce notice management overhead | Time to post new notice | <2 minutes | Simple form-based workflow |

## 3. Non-Goals / Out of Scope

• User accounts, JWT login, password reset, or per-user permissions beyond organizer vs reader
• AI/LLM content generation, email or Slack notifications  
• File attachments, rich media, comments on notices
• Multi-tenant or public internet exposure

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| Employee/Reader | Browse current company announcements | Filter active notices by category, search for specific topics |
| Organizer | Post and manage company communications | Create notices with scheduling, manage categories, archive outdated content |
| Anonymous/Unauthenticated | System health verification | Health check endpoint for ops monitoring |

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|---------------------------------------------|
| FR-1 | Browse active notices with filtering | P0 | Given active notices exist / When user visits browse page / Then only non-archived, currently-scheduled notices appear with category filter options |
| FR-2 | Search notices by title and body content | P0 | Given notices with varied content / When user enters search terms / Then partial, case-insensitive matches in title or body are returned |
| FR-3 | Create notices with organizer authentication | P0 | Given valid organizer secret / When organizer submits notice form / Then notice is saved with category, title, body, author, and optional publish window |
| FR-4 | Manage notice categories | P1 | Given organizer secret / When organizer creates category with unique name / Then category is available for notice assignment |
| FR-5 | Schedule notices with publish windows | P1 | Given start/end dates on notice / When current time is outside window / Then notice does not appear in active browse view |
| FR-6 | Archive notices for historical record | P1 | Given existing notice / When organizer marks as archived / Then notice is hidden from browse but preserved in database |
| FR-7 | Validate notice-category relationships | P1 | Given notice creation request / When referencing non-existent category / Then request fails with clear error message |
| FR-8 | Paginate large notice lists | P2 | Given more than 20 notices / When accessing list endpoint / Then response includes pagination metadata and page controls |

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance | API response time <200ms for list operations | Response time monitoring | (Assumption) |
| NFR-2 | Security/Privacy | Organizer secret validation on all write operations | Authentication logging | Shared secret model as specified |
| NFR-3 | Availability | 99% uptime during business hours | Health check endpoint monitoring | (Assumption) |
| NFR-4 | Scalability | Handle 1000+ notices and 100+ concurrent users | Load testing | (Assumption for mid-size company) |
| NFR-5 | Observability | Request logging and error tracking | Log analysis and alert configuration | (Assumption) |
| NFR-6 | Data retention | Archived notices retained indefinitely | Database backup verification | Historical record requirement |
| NFR-7 | Operability | Clear error messages in UI for API failures | User experience testing | Specified requirement for API down scenarios |

## 7. Data & Integrations

**Core Entities:**
- Notice: id, title, body (text), category_id, author_display_name, start_date (optional), end_date (optional), archived (boolean), created_at, updated_at
- Category: id, name (unique), description (optional), created_at

**External Systems:**
- None specified for MVP

**APIs:**
- Internal FastAPI serving notices and categories
- Streamlit UI consuming REST endpoints

## 8. Analytics & Observability

**Logging:**
- API request/response logging with timing
- Organizer authentication attempts
- Notice CRUD operations with author tracking

**Metrics:**
- Notice creation/update/archive rates
- Category usage distribution
- Search query patterns (Assumption)

**Alerts:**
- API health check failures
- Database connection issues (Assumption)

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Shared organizer secret compromise | Unauthorized notice management | Environment-based secret rotation capability; audit logging |
| API downtime during critical announcements | Communication disruption | Clear UI error messaging; health monitoring |
| Database performance with growing notice history | Slow response times | Pagination implementation; database indexing strategy |
| Category misconfiguration breaking notice creation | Organizer workflow disruption | Category validation and reference integrity checks |

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What is the specific organizer secret rotation process? | DevOps/Security team |
| 2 | Should there be backup/export functionality for notice history? | Product team |
| 3 | What are the specific database performance requirements as notice volume grows? | Engineering team |
| 4 | Are there any content guidelines or approval workflows for sensitive notices? | Internal Communications team |

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | Streamlit | Browser-based interface for both browsing and management |
| API | FastAPI under `target-apps/notice-board-ui/` | REST + OpenAPI at /docs |
| UI location | `ui/streamlit_app.py` when Streamlit | HTTP client to API only — never import `app/` from Streamlit |
| Auth for UI | Shared organizer secret for write operations | Streamlit stores secret in session state for management functions |

## Appendix: Assumptions

• Mid-size company implies ~100-500 employees for scaling estimates
• Business hours availability target (99%) rather than 24/7
• Standard database indexing for search performance
• No specific compliance requirements (GDPR, SOX, etc.) mentioned
• English-only content and search for MVP
• Internal network deployment (not public internet)
• Standard HTTP status codes and REST conventions
• SQLite or PostgreSQL database (not specified in brief)
