# Audit Finding Tracker — Solution Design

## 1. Summary
Internal audit system replacing Excel-based finding management with centralized workflow, immutable audit trails, and executive reporting. PostgreSQL for structured data, S3 for evidence files, FastAPI REST API. TBD: File size limits, retention policies.

## 2. Stack
| Layer | Technology |
|-------|------------|
| API Gateway | AWS API Gateway + WAF |
| Application | FastAPI on ECS Fargate |
| Authentication | AWS Cognito + JWT |
| Database | PostgreSQL RDS |
| File Storage | S3 bucket |
| Infrastructure | VPC, ALB, CloudWatch |

## 3. Data model
| Table / collection | Columns (name type PK/FK UNIQUE) | Indexes / constraints |
|--------------------|----------------------------------|------------------------|
| users | id UUID PK, cognito_sub VARCHAR UNIQUE, email VARCHAR, role ENUM, created_at TIMESTAMP | idx_users_email, idx_users_role |
| audits | id UUID PK, title VARCHAR, description TEXT, status ENUM, created_by UUID FK, created_at TIMESTAMP, version INTEGER | idx_audits_status, idx_audits_created_by |
| findings | id UUID PK, audit_id UUID FK, title VARCHAR, description TEXT, severity ENUM, status ENUM, assigned_to UUID FK, due_date DATE, created_by UUID FK, created_at TIMESTAMP, version INTEGER | idx_findings_status_severity_due, idx_findings_assigned_to |
| evidence_files | id UUID PK, finding_id UUID FK, filename VARCHAR, s3_key VARCHAR, file_size BIGINT, mime_type VARCHAR, uploaded_by UUID FK, uploaded_at TIMESTAMP | idx_evidence_finding_id |
| status_history | id UUID PK, finding_id UUID FK, from_status ENUM, to_status ENUM, changed_by UUID FK, changed_at TIMESTAMP, comment TEXT | idx_status_history_finding_date |
| finding_comments | id UUID PK, finding_id UUID FK, author_id UUID FK, content TEXT, created_at TIMESTAMP, parent_id UUID FK | idx_comments_finding_created |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | /api/v1/auth/login | LoginRequest(email, password) | TokenResponse(access_token, user) | Cognito integration |
| GET | /api/v1/audits | AuditListParams(status, limit, offset) | AuditListResponse(audits, total) | Paginated list |
| POST | /api/v1/audits | CreateAuditRequest(title, description) | AuditResponse(audit) | Creates audit |
| GET | /api/v1/findings | FindingListParams(audit_id, status, assigned_to) | FindingListResponse(findings, total) | Role-scoped data |
| POST | /api/v1/findings | CreateFindingRequest(audit_id, title, severity, assigned_to, due_date) | FindingResponse(finding) | Version = 1 |
| PUT | /api/v1/findings/{id}/status | UpdateStatusRequest(status, comment) | FindingResponse(finding) | If-Match header required |
| POST | /api/v1/findings/{id}/evidence | MultipartFile(file) | EvidenceResponse(evidence) | S3 upload |
| GET | /api/v1/findings/{id}/history | - | StatusHistoryResponse(history) | Immutable audit trail |
| POST | /api/v1/findings/{id}/comments | CreateCommentRequest(content, parent_id) | CommentResponse(comment) | Threaded discussions |
| GET | /api/v1/reports/executive | ReportParams(date_range, department) | ExecutiveReportResponse(overdue, severity_dist, dept_summary) | Executives only |

## 5. Rules
- Auth / RBAC: auditor (all findings CRUD), assignee (own findings read/update), executive (all read + reports), anonymous (/health only)
- Audit: All status transitions logged to status_history with actor, timestamp, comment; append-only table
- Idempotency: Finding status enum (draft, assigned, in_progress, pending_verification, verified, closed); evidence required for pending_verification
- Optimistic locking: version field incremented on updates, If-Match header validation returns 409 on stale data
- File uploads: S3 storage with metadata in evidence_files table, file size limits enforced
- Status workflow: draft→assigned→in_progress→pending_verification→verified→closed (invalid transitions return 422)

## 6. DB delivery
1. Migration order: `001_users.sql`, `002_audits.sql`, `003_findings.sql`, `004_evidence_files.sql`, `005_status_history.sql`, `006_finding_comments.sql`, `007_indexes.sql`
2. Seed data: 3 users (auditor, assignee, executive), 2 audits, 12 findings across all statuses with evidence files and status history
3. Athena or NoSQL: S3 bucket for evidence file storage with lifecycle policies
