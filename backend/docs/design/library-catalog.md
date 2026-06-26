# Library Catalog API — Solution Design

## 1. Summary
Corporate library REST API for book borrowing with date-aware loan management, FIFO hold queues, and member authentication. PostgreSQL backend with FastAPI serving 12 core endpoints for librarians and authenticated members.

## 2. Stack
| Layer | Technology |
|-------|------------|
| API | FastAPI + Pydantic |
| Database | PostgreSQL 15+ |
| Cache | Redis (sessions) |
| Auth | Header-based validation |
| Testing | pytest + testcontainers |

## 3. Data model
| Table / collection | Columns (name type PK/FK UNIQUE) | Indexes / constraints |
|--------------------|----------------------------------|------------------------|
| books | id UUID PK, isbn VARCHAR UNIQUE, title VARCHAR, author VARCHAR, total_copies INTEGER, created_at TIMESTAMP | idx_books_isbn, idx_books_title_author |
| members | id UUID PK, email VARCHAR UNIQUE, member_key VARCHAR UNIQUE, name VARCHAR, created_at TIMESTAMP | idx_members_email, idx_members_key |
| loans | id UUID PK, book_id UUID FK, member_id UUID FK, checkout_at TIMESTAMP, due_at TIMESTAMP, returned_at TIMESTAMP NULL | idx_loans_book_member, idx_loans_due_at, unique(book_id, member_id) WHERE returned_at IS NULL |
| holds | id UUID PK, book_id UUID FK, member_id UUID FK, placed_at TIMESTAMP, fulfilled_at TIMESTAMP NULL, cancelled_at TIMESTAMP NULL | idx_holds_book_placed, idx_holds_member, unique(book_id, member_id) WHERE fulfilled_at IS NULL |
| audit_log | id SERIAL PK, entity_type VARCHAR, entity_id UUID, action VARCHAR, member_id UUID NULL, timestamp TIMESTAMP, details JSONB | idx_audit_timestamp, idx_audit_entity |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | /books | query: str, available_only: bool | books: List[BookResponse] | Anonymous search |
| POST | /loans | book_id: UUID | loan: LoanResponse | Member checkout |
| GET | /loans/mine | - | loans: List[LoanResponse] | Member's active/recent loans |
| POST | /holds | book_id: UUID | hold: HoldResponse | Place hold on unavailable book |
| GET | /holds/mine | - | holds: List[HoldResponse] | Member's active holds |
| POST | /books | title: str, author: str, isbn: str, total_copies: int | book: BookResponse | Librarian only |
| PATCH | /books/{id} | title: str, author: str, total_copies: int | book: BookResponse | Librarian only |
| DELETE | /books/{id} | - | - | Librarian only, 409 if active loans |
| POST | /members | email: str, name: str | member: MemberResponse | Librarian only |
| PUT | /loans/{id}/return | - | loan: LoanResponse | Return book, auto-fulfill holds |

## 5. Rules
- Auth: Header `X-Member-Key` for members, `X-Librarian-Token` for librarians
- RBAC: Members access own loans/holds only; librarians access all operations
- Audit: Log all checkouts, returns, hold placements, book/member CRUD
- Loan limits: Max 5 active loans per member (configurable)
- Due dates: LOAN_DAYS environment variable (default 14 days)
- Hold queue: FIFO by `placed_at`, auto-fulfill oldest on return
- Availability: `available_copies = total_copies - COUNT(active_loans)`
- Overdue: Computed field `is_overdue = due_at < NOW() AND returned_at IS NULL`

## 6. DB delivery
1. Migration order: `001_books.sql`, `002_members.sql`, `003_loans.sql`, `004_holds.sql`, `005_audit_log.sql`
2. Seed data: 10 sample books (tech/business titles), 3 test members, 2 active loans for testing
3. Indexes: Composite indexes on foreign keys, date fields for overdue queries
