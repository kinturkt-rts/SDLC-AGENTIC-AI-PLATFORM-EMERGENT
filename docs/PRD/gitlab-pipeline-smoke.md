# Team Notice Board API

## 1. Overview

Internal teams currently post announcements, reminders, and wins in Slack where they get buried and become hard to reference. There is no simple read API for dashboards or bots to surface "what's active this week." This project delivers a Team Notice Board API that allows anyone to read active notices while organizers with a shared API key can create, update, and archive notices. The solution uses FastAPI with Postgres and provides Swagger documentation, serving as an end-to-end test for the SDLC agent pipeline while following Pattern B (Postgres CRUD + API-key auth).

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Pipeline validation | Full SDLC agent chain completion | 100% success rate | product-agent → architect-agent → database-agent → developer-agent → gitlab-agent |
| API functionality | All endpoints return correct responses | 100% test coverage | Health, categories, notices CRUD with proper auth |
| GitLab integration | Successful branch publish | Artifacts appear in sdlc/gitlab-pipeline-smoke | PRD, design, SQL, FastAPI app, tests |
| Developer experience | Local development works | uvicorn + Swagger /docs accessible | After RDS apply and .env setup |

## 3. Non-Goals / Out of Scope

- JWT/login authentication system
- Bedrock/LLM integration
- pgvector/RAG capabilities
- Streamlit/React UI components
- Email notifications
- Redis caching
- S3 storage
- Terraform infrastructure
- Automatic GitLab MR creation from run-sdlc.ps1

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| Anonymous reader | View active team notices | GET /notices to see current announcements for dashboards/bots |
| Team organizer | Manage notices and categories | POST/PATCH notices with API key for announcements, reminders, wins |
| Dashboard developer | Integrate notice data | Consume REST API endpoints for displaying team updates |
| Bot developer | Surface active notices | Query filtered notices by category or search terms |

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|---------------------------------------------|
| FR-1 | Health check endpoint | P0 | Given API is running / When GET /health called / Then return 200 with {"status":"ok","service":"gitlab-pipeline-smoke"} |
| FR-2 | Category management with API key auth | P0 | Given valid API key / When POST /categories with name and description / Then create category and return 201 / Given invalid key / Then return 401 |
| FR-3 | Notice CRUD operations | P0 | Given valid API key / When POST /notices with title, body, category_id, author_name / Then create notice and return 201 / Given missing API key / Then return 401 |
| FR-4 | Public notice listing with filters | P0 | Given no auth required / When GET /notices?active_only=true / Then return paginated list excluding archived, expired, and future notices |
| FR-5 | Notice search functionality | P1 | Given no auth required / When GET /notices?q=searchterm / Then return notices with case-insensitive partial match on title OR body |
| FR-6 | Notice archival | P1 | Given valid API key / When POST /notices/{id}/archive / Then set is_archived=true and return 204 / Given already archived / Then return 204 idempotently |
| FR-7 | Category uniqueness validation | P1 | Given valid API key / When POST /categories with duplicate name / Then return 409 conflict error |
| FR-8 | Date validation for notices | P1 | Given valid API key / When POST /notices with ends_at < starts_at / Then return 422 validation error |

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance | API response time < 200ms | Load testing with typical payloads | For list and single item endpoints |
| NFR-2 | Security | API key authentication required for writes | Penetration testing of auth bypass attempts | 401 returned for missing/invalid keys |
| NFR-3 | Availability | 99.9% uptime during business hours | Health check monitoring | (Assumption) |
| NFR-4 | Data integrity | ACID compliance for all database operations | Transaction testing and rollback scenarios | PostgreSQL default isolation level |
| NFR-5 | Scalability | Support 1000+ notices with pagination | Performance testing with large datasets | Offset/limit pagination implementation |
| NFR-6 | Observability | Structured logging for all API calls | Log aggregation and monitoring setup | FastAPI request/response logging |
| NFR-7 | Data retention | Soft delete via archival flag | Verify archived notices excluded from active lists | No hard deletion of notice records |

## 7. Data & Integrations

**Database Entities:**
- categories: id (uuid PK), name (text unique 1-60 chars), description (text nullable max 240), created_at
- notices: id (uuid PK), category_id (FK), title (1-120 chars), body (1-4000 chars), author_name (1-80 chars), starts_at, ends_at, is_archived (bool), created_at, updated_at

**External Systems:**
- PostgreSQL database via DATABASE_URL environment variable
- GitLab repository for artifact publishing via GITLAB_* environment variables

**Seed Data:**
- 3 default categories: General, HR, Engineering
- 5 sample notices with mix of active, future, expired, and archived states

## 8. Analytics & Observability

- FastAPI automatic request/response logging
- Health check endpoint for monitoring
- Database connection health monitoring
- API key usage tracking in logs
- Error rate monitoring for 4xx/5xx responses
- Response time metrics collection

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| API key exposure in logs | High - unauthorized access | Ensure API keys are masked in all logging output |
| Database connection failures | High - service unavailable | Implement connection retry logic and health checks |
| Large notice body causing performance issues | Medium - slow responses | Enforce 4000 character limit on notice body field |
| Timezone handling for starts_at/ends_at | Medium - incorrect filtering | Use timestamptz data type and UTC standardization |
| Pipeline agent chain failure | Medium - development blocker | Implement retry mechanism and clear error reporting |

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What is the expected concurrent user load? | Product Owner |
| 2 | Should we implement rate limiting per API key? | Technical Lead |
| 3 | How long should archived notices be retained? | Business Stakeholder |
| 4 | What monitoring/alerting tools will be integrated? | DevOps Team |
| 5 | Should notice body support rich markdown rendering? | UX Team |

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | API-only (Swagger) | Swagger UI available at /docs endpoint |
| API | FastAPI under `target-apps/gitlab-pipeline-smoke/` | REST + OpenAPI specification |
| UI location | N/A - API only | No Streamlit or React components |
| Auth for API | API key via X-API-Key header | Single shared key from environment variable |

## Appendix: Assumptions

- Single API key shared among all organizers is sufficient for MVP
- PostgreSQL schema name gitlab_pipeline_smoke is acceptable
- UTC timezone handling is adequate for starts_at/ends_at fields
- 1000+ notices represents reasonable scale for MVP
- Swagger UI documentation is sufficient for API consumer onboarding
- Soft delete via is_archived flag meets compliance requirements
- Case-insensitive search without full-text indexing is adequate
- Standard FastAPI error handling meets user experience needs
- Agent pipeline success criteria are well-defined in existing tooling
