# Contact Directory API

## 1. Overview

The Contact Directory API is an internal tool that enables teams to store and retrieve colleague contact information through a simple REST interface. The system maintains contact cards with basic information (name, email, department, phone) and department organizational data. The solution uses a tiered access model where anyone can browse contacts via GET endpoints, while write operations require API key authentication. This serves as a validation project for the SDLC chain on Pattern B (Postgres CRUD) architecture, providing more complexity than in-memory solutions while avoiding advanced authentication mechanisms like JWT or external integrations.

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| SDLC validation | Successful handoff through product → architect → database-agent → developer-agent → qa-agent | 100% completion | Primary validation objective |
| API functionality | All CRUD operations working for contacts and departments | 100% endpoint coverage | Core functional requirement |
| Authentication coverage | Protected endpoints reject unauthorized requests | 100% of write operations require API key | Security baseline |
| Data integrity | No data corruption or constraint violations | Zero data integrity issues | Database reliability |
| Test coverage | Comprehensive test suite covering key scenarios | All specified test cases pass | Quality assurance |

## 3. Non-Goals / Out of Scope

- JWT authentication or user login systems
- Bedrock/LLM integration
- pgvector or RAG functionality  
- Streamlit or React UI components
- Redis caching layer
- S3 integration
- Docker containerization (handled by devops-agent later)
- OAuth or external authentication providers
- Password hashing or user management

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| Anonymous API Consumer | Browse contact directory | Retrieve contact information and department listings for internal directory lookups |
| System Integrator | Maintain contact data | Create, update, and manage contact records through automated systems or admin tools |
| Development Team | Validate SDLC process | Use as reference implementation for Pattern B architecture validation |
| QA Team | Test API functionality | Execute comprehensive testing scenarios for CRUD operations and authentication |

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|---------------------------------------------|
| FR-1 | Health check endpoint | P0 | Given the API is running / When GET /health is called / Then return 200 with {"status":"ok","service":"contacts-api"} |
| FR-2 | Browse contacts anonymously | P0 | Given valid contact data exists / When GET /contacts is called without auth / Then return paginated list with items, total, limit, offset |
| FR-3 | Create contacts with API key | P0 | Given valid API key header / When POST /contacts with valid data / Then return 201 and create contact record |
| FR-4 | Reject unauthorized writes | P0 | Given missing or invalid API key / When attempting POST/PATCH/DELETE operations / Then return 401 with "Invalid or missing API key" |
| FR-5 | Search contacts by name/email | P1 | Given contacts exist / When GET /contacts?q=searchterm / Then return case-insensitive partial matches on full_name or email |
| FR-6 | Manage departments | P1 | Given API key / When creating/updating departments / Then enforce unique code constraint and return appropriate status codes |
| FR-7 | Soft delete contacts | P1 | Given existing contact and API key / When DELETE /contacts/{id} / Then set is_active=false and return 204 |
| FR-8 | Validate department relationships | P1 | Given contact creation request / When department_id doesn't exist / Then return 404 error |
| FR-9 | Enforce email uniqueness | P2 | Given existing contact email / When creating contact with duplicate email / Then return 409 conflict error |

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Security | API key authentication for write operations | Verify 401 responses for missing/invalid keys | Simple shared key model only |
| NFR-2 | Performance | Response time <500ms for typical queries | Load testing with pytest | Single instance deployment (Assumption) |
| NFR-3 | Availability | 99% uptime during business hours | Health check monitoring | Development/internal use (Assumption) |
| NFR-4 | Data integrity | Zero data corruption, foreign key constraints enforced | Database constraint validation tests | Postgres ACID compliance |
| NFR-5 | Scalability | Support 10,000 contacts with sub-second queries | Query performance testing | Internal team usage (Assumption) |
| NFR-6 | Observability | Request logging and error tracking | Log analysis and monitoring setup | Standard FastAPI logging (Assumption) |
| NFR-7 | Operability | Simple deployment with environment variables | Deployment verification checklist | Single configuration file approach |

## 7. Data & Integrations

**Core Entities:**
- departments: id (uuid), name (text 1-80 chars), code (text 2-10 uppercase, unique), created_at
- contacts: id (uuid), department_id (FK), full_name (text 1-120), email (unique), phone (optional, max 30), title (optional, max 80), is_active (boolean), created_at, updated_at

**External Systems:**
- PostgreSQL database with contacts_api schema
- Environment variable configuration (.env file)

**APIs:**
- RESTful HTTP API with JSON payloads
- Swagger documentation at /docs endpoint

## 8. Analytics & Observability

**Logging:**
- Request/response logging for all API endpoints
- Authentication failure tracking
- Database operation logging

**Metrics:**
- API endpoint response times
- Request volume by endpoint
- Authentication success/failure rates
- Database connection health

**Alerts:** (Assumption)
- Health check failures
- High error rates on write operations
- Database connectivity issues

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Shared API key compromise | Medium - unauthorized data modification | Use environment variables, document key rotation process |
| Database constraint violations | Low - data integrity issues | Comprehensive validation in API layer and database constraints |
| Missing test coverage | Medium - production bugs | Specified test scenarios must be implemented and passing |
| Performance degradation with scale | Low - slower response times | Implement database indexing on commonly queried fields |
| Configuration errors | Medium - deployment failures | Provide clear .env.example and setup documentation |

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What is the expected contact volume for capacity planning? | Product Manager |
| 2 | Should we implement rate limiting on the API endpoints? | Architect |
| 3 | What monitoring/alerting infrastructure will be available? | DevOps |
| 4 | How should API key rotation be handled in production? | Security team |
| 5 | Are there specific data retention requirements for inactive contacts? | Compliance team |

## Appendix: Assumptions

- Single shared API key for all write operations (no per-user keys)
- Internal-only usage with moderate traffic volumes
- Standard business hours availability requirements
- SQLite fallback for testing environments is acceptable
- Basic FastAPI logging is sufficient for observability
- No specific compliance requirements (GDPR, SOC2, etc.)
- Development team has PostgreSQL administration capabilities
- Standard HTTP response codes and JSON error formats are acceptable
- No advanced search requirements beyond simple text matching
- Soft delete approach is preferred over hard delete for audit purposes
