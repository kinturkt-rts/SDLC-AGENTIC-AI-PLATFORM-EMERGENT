# Library Catalog API

## 1. Overview

A small corporate library needs a digital system to manage physical book borrowing by employees. The current process is manual with no tracking of loans, due dates, or book availability. The proposed solution is a REST API that enables librarians to manage the book catalog and member registry, while allowing authenticated members to check out books, track their loans, and place holds on unavailable items.

The API implements date-aware business logic for loan periods, overdue calculations, and FIFO hold queue management. Built with FastAPI, PostgreSQL, and pytest, it provides Swagger documentation at /docs for demonstrations and testing.

This system validates SDLC processes around PostgreSQL CRUD operations with complex date mathematics and relational data queries, representing a different architectural pattern from simpler contact management APIs.

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Enable digital book tracking | API endpoints implemented and functional | 100% of core endpoints (12 total) | Replace manual shelf management |
| Accurate loan period management | Date calculations correct in all scenarios | 100% test coverage on date logic | 14-day default, configurable via env |
| Prevent book conflicts | Concurrent loan attempts handled correctly | 0 double-checkouts of same copy | Proper available_copies calculation |
| Fair hold queue system | FIFO order maintained across all scenarios | 100% correct queue position | Auto-fulfillment on returns |
| System reliability | API uptime and response time | 99% uptime, <200ms response | Corporate library hours only |

## 3. Non-Goals / Out of Scope

- JWT authentication or advanced RBAC systems
- Integration with physical barcode scanners or RFID systems
- Email notifications for due dates or hold fulfillment
- Fine calculation or payment processing
- Mobile application or web frontend (API only)
- Integration with external library systems
- Book recommendation or search ranking algorithms
- Multi-library or branch support

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| Employee (Member) | Borrow books for personal/professional development | Search catalog, check out available books, track personal loans |
| Librarian | Manage book inventory and member access | Add new books, register employees, monitor overdue items |
| Anonymous User | Browse available books without commitment | Search catalog to see what's available before becoming member |
| System Administrator | Monitor API health and performance | Check system status and validate configurations |

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|---------------------------------------------|
| FR-1 | Book catalog search for anonymous users | P0 | Given anonymous access / When GET /books with query parameter / Then return matching books by title or author |
| FR-2 | Member book checkout with date calculation | P0 | Given authenticated member / When POST /loans with valid book_id / Then create loan with due_at = checkout_date + LOAN_DAYS |
| FR-3 | Automatic overdue status computation | P0 | Given active loan past due date / When GET loan data / Then is_overdue field returns true |
| FR-4 | FIFO hold queue management | P0 | Given multiple holds on same book / When book returned / Then fulfill oldest unfulfilled hold first |
| FR-5 | Member loan limit enforcement | P1 | Given member with 5 active loans / When attempting 6th checkout / Then return 409 Conflict |
| FR-6 | Book availability calculation | P0 | Given book with N total_copies and M active loans / When checking availability / Then available_copies = N - M |
| FR-7 | Librarian catalog management | P0 | Given librarian authentication / When POST/PATCH/DELETE books or members / Then perform operations successfully |
| FR-8 | Member personal loan tracking | P1 | Given authenticated member / When GET /loans/mine / Then return member's active and 30 most recent loans |
| FR-9 | Hold queue position tracking | P1 | Given member placing hold / When POST /holds / Then return current queue_position |
| FR-10 | Safe book deletion with conflict check | P2 | Given book with active loans / When DELETE /books/{id} / Then return 409; otherwise hard delete |

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance | <200ms response time for 95% of requests | API monitoring and load testing | (Assumption based on corporate network) |
| NFR-2 | Security | Header-based authentication validation on all protected endpoints | Security testing and penetration tests | Simplified auth model for MVP |
| NFR-3 | Availability | 99% uptime during business hours | Monitoring and alerting systems | Corporate library hours only |
| NFR-4 | Data Integrity | 100% ACID compliance for concurrent operations | Database transaction testing | Critical for loan/hold conflicts |
| NFR-5 | Scalability | Support up to 1000 concurrent users | Load testing with simulated traffic | (Assumption based on corporate size) |
| NFR-6 | Observability | Comprehensive logging of all operations | Log analysis and monitoring dashboards | Required for debugging date logic |
| NFR-7 | Data Retention | Maintain loan history for audit purposes | Database design and backup verification | No automatic purging in MVP |

## 7. Data & Integrations

**Core Entities:**
- Books: UUID primary key, ISBN uniqueness constraint, copy tracking
- Members: UUID primary key, email uniqueness, auto-generated member_key
- Loans: Foreign keys to books and members, timestamp tracking for checkout/due/return
- Holds: Foreign keys to books and members, FIFO queue management via timestamps

**External Dependencies:**
- PostgreSQL database for persistent storage
- Environment configuration for LOAN_DAYS parameter
- FastAPI framework for REST API implementation

**No external API integrations required for MVP.**

## 8. Analytics & Observability

**Logging Requirements:**
- All authentication attempts (success/failure)
- Book checkout and return operations with timestamps
- Hold placement and fulfillment events
- Overdue calculation triggers
- Database constraint violations and errors

**Metrics to Track:**
- Book checkout frequency by title/author
- Average loan duration vs. policy limit
- Hold queue length and fulfillment time
- Member activity patterns
- System performance (response times, error rates)

**Alerting:**
- Database connection failures
- Authentication system errors
- Unexpected spikes in overdue items

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Race condition in book checkout | Double-booking of last available copy | Database constraints and proper transaction isolation |
| Incorrect date mathematics | Wrong due dates or overdue calculations | Comprehensive pytest coverage with timezone handling |
| Member key exposure | Unauthorized access to member functions | Secure key generation, logging of suspicious activity |
| Database performance with date queries | Slow response times for overdue calculations | Proper indexing on date fields, query optimization |
| Hold queue corruption | FIFO order violations | Atomic operations for hold fulfillment, audit logging |

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | Should the system handle timezone conversions for due dates? | Engineering team |
| 2 | What is the maximum expected number of books and members? | Product owner / Librarian |
| 3 | Should there be a grace period before marking loans overdue? | Librarian / HR policy |
| 4 | How should the system handle book renewals in future iterations? | Product owner |
| 5 | What backup and disaster recovery requirements exist? | IT operations team |
| 6 | Should anonymous users see real-time availability or cached counts? | Engineering team |

## Appendix: Assumptions

- Corporate library operates during standard business hours only
- Maximum 1000 employees in the organization requiring member accounts
- Network latency within corporate environment is minimal
- PostgreSQL is the approved database technology
- No integration with existing HR systems for member management
- English language support only for book titles and author names
- Standard UTC timestamp handling is sufficient for MVP
- Swagger UI at /docs is acceptable for initial user interface needs
- No requirement for bulk operations (batch book uploads, etc.)
- Member keys have sufficient entropy for security in corporate environment
