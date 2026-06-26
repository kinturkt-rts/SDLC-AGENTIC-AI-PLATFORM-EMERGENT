# Hot Desk Booking API

## 1. Overview

Engineering teams in hybrid offices need to reserve hot desks for the days they come into the office. Each desk is located in a specific zone (north, south, lab), and employees can book desks for specific dates with time slots (full-day, AM, or PM). The system must prevent overlapping bookings on the same desk and time slot combination while allowing admins to blackout desks for maintenance periods.

This API-only solution provides a booking ledger without real-time check-in flows or QR code integration. The primary focus is on robust CRUD operations with PostgreSQL, multi-column uniqueness constraints, and time-slot conflict detection to validate the SDLC chain for complex database modeling scenarios.

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Prevent double-booking conflicts | Booking conflict rate | 0% (enforced by DB constraints) | UNIQUE constraint on (desk_id, booking_date, slot) |
| Validate SDLC chain for complex schemas | Test coverage on conflict scenarios | >90% | Focus on multi-column uniqueness and overlap detection |
| API response performance | P95 response time | <200ms | For booking creation and availability queries |
| System availability | Uptime | 99.5% | Standard for internal tools |

## 3. Non-Goals / Out of Scope

• Recurring bookings or team-level reservations
• Notifications or calendar integration
• Check-in / no-show tracking (deferred to Phase 2)
• Payment or cost allocation
• Real-time check-in flows
• QR code generation or scanning
• Mobile app interface
• Reporting dashboards

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| Employee | Reserve workspace for office days | Book a hot desk for a specific date and time slot |
| Admin | Manage desk inventory and maintenance | Create/disable desks and blackout periods for maintenance |
| Anonymous User | Check desk availability | View available desks without authentication |

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|---------------------------------------------|
| FR-1 | Prevent overlapping desk bookings | P0 | Given a desk is booked for a specific date+slot / When another user tries to book the same desk+date+slot / Then return 409 with conflicting booking ID |
| FR-2 | Enforce one booking per user per date | P0 | Given a user has a booking on a specific date / When they try to book another desk on the same date / Then return 409 with validation error |
| FR-3 | Handle time slot conflicts (full vs am/pm) | P0 | Given a desk has an AM booking / When someone tries to book full-day for same desk+date / Then return 409 conflict |
| FR-4 | Restrict booking window to 30 days | P1 | Given current date / When user tries to book >30 days in future or past dates / Then return 422 with date range error |
| FR-5 | Block bookings during blackout periods | P0 | Given a desk has active blackout period / When user tries to book during blackout dates / Then return 409 with blackout reason |
| FR-6 | Provide availability query by date and zone | P1 | Given a date and optional zone filter / When GET /availability is called / Then return per-desk availability slots |
| FR-7 | Allow users to view and cancel their bookings | P1 | Given authenticated user / When GET /bookings/mine is called / Then return user's bookings with pagination |
| FR-8 | Restrict booking deletion to owner or admin | P0 | Given a booking owned by User A / When User B tries to DELETE (non-admin) / Then return 403 forbidden |

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance | <200ms P95 response time | API monitoring on booking endpoints | (Assumption) |
| NFR-2 | Security | Token-based authentication | X-User-Token and X-Admin-Key validation | Per auth spec |
| NFR-3 | Availability | 99.5% uptime | Health check monitoring | (Assumption) |
| NFR-4 | Data Integrity | UNIQUE constraints enforced | Database constraint violations return 409 | Critical for conflict detection |
| NFR-5 | Scalability | Handle 1000 concurrent users | Load testing on booking creation | (Assumption) |
| NFR-6 | Observability | Structured logging for conflicts | Log all 409 responses with context | For debugging booking issues |
| NFR-7 | Data Retention | 1 year booking history | Automated archival process | (Assumption) |

## 7. Data & Integrations

**Database Entities:**
- zones: id (uuid), name (text unique: north|south|lab), created_at
- desks: id (uuid), zone_id (FK), label (text), is_active (bool), created_at  
- users: id (uuid), email (text unique), full_name (text), user_token (text unique), created_at
- bookings: id (uuid), desk_id (FK), user_id (FK), booking_date (date), slot (enum: full|am|pm), created_at
- blackouts: id (uuid), desk_id (FK), starts_on (date), ends_on (date), reason (text), created_at

**Key Constraints:**
- UNIQUE (desk_id, booking_date, slot) on bookings table
- Foreign key relationships with cascading rules

**External Integrations:** None (API-only system)

## 8. Analytics & Observability

**Logging:**
- All booking conflicts (409 responses) with desk_id, date, slot details
- Authentication failures and unauthorized access attempts
- Blackout period violations

**Metrics:**
- Booking creation success/failure rates
- API endpoint response times
- Database constraint violation frequency
- Peak usage patterns by time slot and zone

**Alerts:**
- Database connection failures
- Unusual spike in 409 conflict responses
- API response time degradation >500ms

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Race conditions in booking creation | Medium | Use database UNIQUE constraints as final arbiter, return 409 on conflict |
| Database performance under high load | High | Index on (desk_id, booking_date, slot) and query optimization |
| Token management complexity | Medium | Simple opaque token mapping, admin key rotation process |
| Time zone handling ambiguity | Medium | Store dates in UTC, document timezone assumptions |

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What is the token rotation strategy for user and admin tokens? | Security team |
| 2 | Should we support partial day blackouts (AM/PM only)? | Product team |
| 3 | What is the maximum number of desks per zone we need to support? | Operations team |
| 4 | Do we need audit trails for admin actions (desk creation, blackouts)? | Compliance team |

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | API-only (Swagger) | FastAPI auto-generated documentation |
| API | FastAPI under `target-apps/hot-desk-booking/` | REST + OpenAPI with conflict handling |
| UI location | N/A | Pure API implementation |
| Auth for API | Custom token validation (X-User-Token, X-Admin-Key) | Middleware validates tokens against database |

## Appendix: Assumptions

• API response time targets based on typical internal tool requirements
• User concurrency estimates for load testing
• Data retention period of 1 year for booking history
• UTC timezone for all date storage and calculations  
• Standard HTTP status codes for REST API responses
• No requirement for real-time notifications or websockets
• PostgreSQL as the database backend based on CRUD focus
• Structured JSON logging format for observability
