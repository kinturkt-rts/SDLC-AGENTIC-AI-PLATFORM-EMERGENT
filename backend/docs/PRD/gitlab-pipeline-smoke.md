# Team Notice Board API

## 1. Overview

Internal teams currently post updates in Slack where they get buried and lack discoverability for dashboards or bots. The Team Notice Board API provides a simple REST API for teams to post notices (announcements, reminders, wins) on a shared board with categorization and time-based visibility controls.

The solution enables anonymous read access for notices and categories via public endpoints, while organizers use API key authentication to create, update, and archive notices. The system automatically handles time-based visibility, filtering out expired or future-scheduled notices from default list views.

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Replace buried Slack updates | Active notices posted weekly | >10 notices/week | Measured via GET /notices analytics |
| Enable dashboard integration | API response time | <200ms p95 | For external systems consuming notices |
| Reduce information fragmentation | Notice categories utilized | 100% of notices categorized | All notices must have valid category_id |
| Support automated consumption | API uptime | 99.5% | Critical for bot/dashboard integrations |

## 3. Non-Goals / Out of Scope

- User authentication with login/JWT tokens
- Streamlit or React UI components
- LLM/AI content generation or analysis
- Email notifications for new notices
- Real-time updates via WebSocket
- File attachments or rich media
- Comment threads on notices
- User management or role-based permissions beyond API key
- Integration with external notification systems

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| Anonymous Reader | View current team announcements | GET /notices to see active notices for dashboard display |
| Dashboard System | Programmatically fetch notices | Automated polling of API endpoints for display integration |
| Team Organizer | Post and manage announcements | Create notices with time windows; archive outdated content |
| Bot Developer | Search and filter notices | Use query parameters to find specific notices by category or content |

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|---------------------------------------------|
| FR-1 | Public notice listing with filtering | P0 | Given active notices exist / When GET /notices called / Then returns paginated list excluding archived and expired notices |
| FR-2 | API key authentication for write operations | P0 | Given valid API key in X-API-Key header / When POST /notices called / Then creates notice with 201 status |
| FR-3 | Category management system | P0 | Given organizer authentication / When POST /categories with unique name / Then creates category with 201 status |
| FR-4 | Time-based notice visibility | P0 | Given notice with ends_at in past / When GET /notices?active_only=true / Then notice excluded from results |
| FR-5 | Notice archival functionality | P1 | Given existing notice ID / When POST /notices/{id}/archive with API key / Then sets is_archived=true with 204 status |
| FR-6 | Search functionality across notices | P1 | Given notices with searchable content / When GET /notices?q=term / Then returns notices with case-insensitive partial match on title or body |
| FR-7 | Notice scheduling with start dates | P2 | Given notice with future starts_at / When GET /notices?active_only=true / Then notice excluded until starts_at reached |

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance | <200ms response time p95 | Load testing with 100 concurrent requests | Critical for dashboard integrations |
| NFR-2 | Security | API key validation on all write operations | Automated security tests verify 401 responses | Single shared API key for MVP |
| NFR-3 | Availability | 99.5% uptime | Monitoring and alerting on service health | (Assumption) |
| NFR-4 | Scalability | Support 1000 notices and 50 categories | Database performance testing | (Assumption) |
| NFR-5 | Data Integrity | Foreign key constraints enforced | Database schema validation tests | category_id must reference valid category |
| NFR-6 | API Documentation | OpenAPI spec available at /docs | Swagger UI accessibility verification | FastAPI auto-generates documentation |
| NFR-7 | Error Handling | Consistent HTTP status codes and error messages | API contract testing | 404 for missing resources, 409 for conflicts, 422 for validation |

## 7. Data & Integrations

**Core Entities:**
- Categories: id (UUID), name (unique, 1-60 chars), description (optional, max 240), created_at
- Notices: id (UUID), category_id (FK), title (1-120 chars), body (1-4000 chars), author_name (1-80 chars), starts_at, ends_at, is_archived, created_at, updated_at

**External Systems:**
- PostgreSQL database with gitlab_pipeline_smoke schema
- GitLab repository for code deployment and CI/CD pipeline

**APIs:**
- REST API with OpenAPI specification
- Health check endpoint for monitoring systems

## 8. Analytics & Observability

**Logging:**
- API request/response logging with request IDs
- Authentication failures and security events
- Database query performance metrics

**Metrics:**
- Notice creation/update/archive rates
- API endpoint response times and error rates
- Database connection pool utilization

**Health Checks:**
- /health endpoint returning service status
- Database connectivity verification
- API key validation monitoring

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| API key compromise | Medium - unauthorized notice management | Use environment variable for API key, plan key rotation process |
| Database performance degradation | High - slow API responses | Index on (is_archived, starts_at DESC) for efficient queries |
| Notice content quality issues | Low - inappropriate content posted | Manual moderation by organizers using archive functionality |
| Category name conflicts | Low - API errors on duplicate names | Database unique constraint with proper 409 error handling |

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What is the expected peak concurrent API usage? | Product Manager |
| 2 | Should we implement soft delete for notices instead of archive flag? | Database Architect |
| 3 | Are there specific compliance requirements for notice data retention? | Legal/Compliance |
| 4 | Should API key have expiration or rotation mechanism? | Security Team |

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | API-only (Swagger) | No Streamlit or React - FastAPI serves OpenAPI docs at /docs |
| API | FastAPI under `target-apps/gitlab-pipeline-smoke/` | REST + OpenAPI with pydantic schemas |
| UI location | N/A | Swagger UI at /docs endpoint only |
| Auth for UI | API key in request headers | X-API-Key header for write operations |

## Appendix: Assumptions

- Single shared API key sufficient for MVP organizer authentication
- PostgreSQL performance adequate for expected notice volume
- 99.5% availability target reasonable for internal tool
- Case-insensitive search sufficient for initial implementation
- Manual moderation acceptable for content quality control
- Standard HTTP status codes meet client integration needs
- OpenAPI documentation sufficient for developer onboarding
- Time zone handling via UTC timestamps in database
- Markdown support in notice body limited to plain text storage
- No backup/disaster recovery requirements specified
