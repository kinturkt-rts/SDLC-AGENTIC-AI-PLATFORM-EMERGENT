# Audit Finding Tracker

## 1. Overview

Internal audit teams currently manage SOC findings in Excel spreadsheets that frequently diverge from reality, creating compliance risks and reducing leadership visibility. The Audit Finding Tracker will provide a centralized system for managing audits, findings, and remediation workflows with full traceability and executive reporting. The system will enforce structured workflows, maintain immutable audit trails of all status changes, and provide role-based access to ensure proper segregation of duties between auditors, assignees, and executives.

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Eliminate Excel-based finding management | Percentage of findings tracked in system vs. Excel | 100% | All audit findings must be managed through the system |
| Improve finding remediation visibility | Average days to status update | <3 days | Track time between status changes |
| Ensure compliance audit trail | Percentage of status changes with immutable history | 100% | All transitions must be logged to status_history table |
| Increase executive visibility | Executive dashboard usage | Daily access | Leadership can view real-time finding status |
| Reduce overdue findings | Percentage of findings past due date | <10% | Measured against total open findings |

## 3. Non-Goals / Out of Scope

- Jira integration for issue management
- Email notifications for status changes
- Multi-tenant architecture for external clients
- Bedrock AI auto-classification of findings
- Advanced reporting beyond executive dashboards
- File versioning for evidence uploads
- Automated remediation workflows

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| Internal Auditor (Priya) | Create and manage audit findings with full visibility | Create audits, assign findings to departments, verify remediation evidence, and close findings |
| Department Assignee | Track and remediate assigned findings | View assigned findings, upload remediation evidence, update status, and communicate with auditors |
| Executive Leadership | Monitor organization-wide audit status | View real-time dashboards showing overdue findings, severity distribution, and department performance |

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|---------------------------------------------|
| FR-1 | Create and manage audits with findings | P0 | Given an authenticated auditor, When they create an audit with findings, Then the audit and findings are stored with proper FK relationships and status tracking |
| FR-2 | Enforce workflow state transitions | P0 | Given a finding in any status, When a user attempts a state transition, Then only valid transitions per the workflow matrix are allowed and invalid transitions return 422 |
| FR-3 | Maintain immutable audit trail | P0 | Given any finding status change, When the transition occurs, Then an append-only record is created in status_history with actor, timestamp, and optional comment |
| FR-4 | Upload and manage evidence files | P1 | Given an assignee remediating a finding, When they upload evidence files, Then files are stored with metadata and required before transitioning to pending_verification |
| FR-5 | Implement optimistic locking | P1 | Given concurrent updates to a finding, When using version control headers, Then stale updates return 409 and successful updates increment the version |
| FR-6 | Generate executive reports | P1 | Given an authenticated executive user, When accessing reports endpoints, Then overdue findings, department summaries, and severity distributions are returned accurately |
| FR-7 | Scope data access by role | P0 | Given different user roles, When accessing findings data, Then assignees see only their assigned findings while auditors and executives see all findings |
| FR-8 | Support finding comments and collaboration | P2 | Given authenticated users working on a finding, When they post comments, Then threaded discussions are maintained with author attribution and timestamps |

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Security | JWT-based authentication with role-based authorization | Security testing, penetration testing | All endpoints except /health require valid JWT |
| NFR-2 | Performance | API response time <500ms for 95th percentile | Load testing, APM monitoring | Critical for executive dashboard responsiveness |
| NFR-3 | Availability | 99.5% uptime during business hours | Uptime monitoring, health checks | /health endpoint must respond within 5 seconds |
| NFR-4 | Data Integrity | Zero data loss for audit trail records | Database constraints, backup verification | status_history table is append-only with no deletes |
| NFR-5 | Scalability | Support 1000+ concurrent findings | Load testing, database indexing | Proper indexes on findings(status, severity, due_date) |
| NFR-6 | Compliance | Immutable audit trail for regulatory requirements | Audit log verification | All finding transitions must be traceable |
| NFR-7 | Operability | Database schema migrations and seed data | Automated deployment scripts | DDL files and seed data for 2 audits, 12 findings |

## 7. Data & Integrations

**Core Entities:**
- Users (auditors, assignees, executives) with role-based permissions
- Audits containing multiple findings with lifecycle management
- Findings with status workflow, evidence attachments, and comment threads
- Evidence files stored in local filesystem with metadata tracking
- Status history maintaining immutable audit trail

**External Systems:**
- Local filesystem for evidence file storage under `data/evidence/`
- Database with proper foreign key relationships and indexing
- JWT authentication service for session management

**APIs:**
- RESTful API with FastAPI framework
- Multipart file upload for evidence attachments
- Role-scoped endpoints with proper authorization

## 8. Analytics & Observability

**Logging:**
- All API requests with user context and response codes
- Finding status transitions with actor and timestamp
- File upload events with metadata and success/failure status

**Metrics:**
- Finding remediation cycle time by department and severity
- Overdue finding trends and patterns
- User activity patterns and system usage

**Alerts:**
- Database connectivity failures through /health endpoint
- Unauthorized access attempts and authentication failures
- File storage capacity and upload failures

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data corruption in status_history | High - Loss of audit trail | Implement append-only constraints, regular backups, and database integrity checks |
| Concurrent finding updates | Medium - Data inconsistency | Enforce optimistic locking with version headers and return 409 on conflicts |
| File system storage limitations | Medium - Evidence upload failures | Monitor disk usage, implement file size limits, and plan for cloud storage migration |
| Role-based access control bypass | High - Security breach | Comprehensive authorization testing and regular security audits |
| Performance degradation with large datasets | Medium - Poor user experience | Implement proper database indexing and query optimization |

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What is the maximum file size limit for evidence uploads? | Product Manager |
| 2 | How long should audit data be retained for compliance purposes? | Legal/Compliance team |
| 3 | Should the system support bulk operations for managing multiple findings? | Product Manager |
| 4 | What backup and disaster recovery requirements exist for audit data? | Infrastructure team |
| 5 | Are there specific compliance frameworks (SOX, GDPR) that must be supported? | Compliance team |

## Appendix: Assumptions

- JWT authentication is sufficient for security requirements
- Local filesystem storage is acceptable for MVP evidence files
- Streamlit is appropriate for the user interface framework
- SQLAlchemy ORM with FastAPI provides adequate performance
- Five user roles (auditor, assignee, executive, anonymous) cover all use cases
- Standard HTTP status codes (409, 422, 403) meet API contract needs
- Database indexes on specified columns will provide adequate query performance
- Seed data with 2 audits and 12 findings represents realistic test scenarios
- Executive users only need read access without file download capabilities
