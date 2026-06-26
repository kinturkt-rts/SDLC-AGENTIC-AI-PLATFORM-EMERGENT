# Library Catalog API

Corporate library REST API for book borrowing with date-aware loan management, FIFO hold queues, and member authentication. Built with FastAPI and PostgreSQL.

## Features

- **Book Management**: Search catalog (anonymous), add/update/delete books (librarian only)
- **Member Management**: Register employees, auto-generate member keys (librarian only)  
- **Loan Tracking**: Check out books, automatic due date calculation, return processing
- **Hold System**: FIFO queue for unavailable books, auto-fulfillment on returns
- **Business Rules**: 14-day loans (configurable), 5-book limit per member, overdue tracking
- **Authentication**: Header-based auth (`X-Member-Key`, `X-Librarian-Token`)

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/books/` | None | Search books by title/author |
| POST | `/books/` | Librarian | Add new book to catalog |
| PATCH | `/books/{id}` | Librarian | Update book details |
| DELETE | `/books/{id}` | Librarian | Delete book (no active loans) |
| POST | `/members/` | Librarian | Register new member |
| POST | `/loans/` | Member | Check out book |
| GET | `/loans/mine` | Member | Get my active/recent loans |
| PUT | `/loans/{id}/return` | Member | Return borrowed book |
| POST | `/holds/` | Member | Place hold on unavailable book |
| GET | `/holds/mine` | Member | Get my active holds |
| DELETE | `/holds/{id}` | Member | Cancel active hold |
| GET | `/health` | None | Health check with database ping |

## Local Development

### Prerequisites

- Python 3.12+
- PostgreSQL 15+ (or use provided SQLite for tests)

### Setup

**Terminal 1: API Server**

From the **repo root** (folder containing `target-apps/`):

```bash
# Navigate to app directory
cd target-apps/library-catalog

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
# Windows:
copy .env.example .env
# macOS/Linux:
cp .env.example .env

# Edit .env file with your database credentials
# Update these variables:
#   DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/library_catalog?sslmode=require
#   POSTGRES_SCHEMA=library_catalog
#   API_KEY=your-member-api-key-here
#   LIBRARIAN_TOKEN=your-librarian-token-here

# Start the API server
uvicorn app.main:app --reload --port 8000
```

**Important**: If `.venv/` is under the app directory, use `uvicorn app.main:app --reload-exclude '.venv' --port 8000` to avoid endless reloads.

The API will be available at: http://localhost:8000

Interactive documentation: http://localhost:8000/docs

### Environment Variables

Update these in your `.env` file:

| Variable | Example | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg://user:password@localhost:5432/library_catalog?sslmode=require` | Postgres connection (URL-encode special chars: # → %23) |
| `POSTGRES_SCHEMA` | `library_catalog` | Database schema name |
| `API_KEY` | `MBR_your-member-key` | Member authentication key |
| `LIBRARIAN_TOKEN` | `LIB_your-librarian-token` | Librarian authentication token |
| `LOAN_DAYS` | `14` | Default loan period in days |
| `MAX_ACTIVE_LOANS` | `5` | Maximum active loans per member |

**Warning**: Every line needs the variable name — paste `DATABASE_URL=postgresql+psycopg://...`, not a bare URL.

### Testing

Run the test suite:

```bash
# From target-apps/library-catalog/ with activated venv
python -m pytest tests/ -v

# Quick run
python -m pytest tests/ -q
```

**Note**: Tests use in-memory SQLite. Passing tests ≠ RDS compatibility proof.

## Manual API Testing (Swagger)

1. Open http://localhost:8000/docs
2. For member endpoints: Click "Authorize", add `X-Member-Key` header with your API key
3. For librarian endpoints: Add `X-Librarian-Token` header with your librarian token
4. Try the endpoints in this order:
   - `POST /members/` (create a member)
   - `POST /books/` (add a book) 
   - `POST /loans/` (checkout the book)
   - `GET /loans/mine` (see your loan)

### cURL Examples

**Search books (anonymous):**
```bash
curl -X GET "http://localhost:8000/books/?query=java" \
  -H "accept: application/json"
```

**Create book (librarian):**
```bash
curl -X POST "http://localhost:8000/books/" \
  -H "accept: application/json" \
  -H "X-Librarian-Token: your-librarian-token-here" \
  -H "Content-Type: application/json" \
  -d '{
    "isbn": "9780134685991",
    "title": "Effective Java",
    "author": "Joshua Bloch",
    "total_copies": 3
  }'
```

**Check out book (member):**
```bash
curl -X POST "http://localhost:8000/loans/" \
  -H "accept: application/json" \
  -H "X-Member-Key: your-member-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "book_id": "book-uuid-from-previous-response"
  }'
```

### PowerShell Example

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/books/" -Method Get `
  -Headers @{"accept" = "application/json"}
```

## RDS Smoke Test

After setting up your `.env` with real PostgreSQL credentials:

1. **Health check**: `GET http://localhost:8000/health`
   - Should return `{"status":"ok","checks":{"api":"ok","database":"ok"}}`

2. **Database connectivity**: `GET http://localhost:8000/books/`
   - Should return empty array `[]` or existing books

### Seed UUIDs

Use these test IDs from the database seed file for RDS testing:

**Books:**
- Effective Java: `550e8400-e29b-41d4-a716-446655440001`
- The Pragmatic Programmer: `550e8400-e29b-41d4-a716-446655440002`
- Spring Boot in Action: `550e8400-e29b-41d4-a716-446655440003`

**Members:**
- Alice Developer: `660e8400-e29b-41d4-a716-446655440001` (key: `MBR_alice_dev_2024`)
- Bob Manager: `660e8400-e29b-41d4-a716-446655440002` (key: `MBR_bob_mgr_2024`)

## Deployment (AWS dev — devops-agent)

**Container settings:**
- Port: `8000`
- Health check: `GET /health`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

**Environment variables:** Same as `.env.example` keys, values from AWS Secrets Manager

**Database:** Use RDS PostgreSQL with schema `library_catalog`

## Architecture

- **FastAPI**: REST API framework with automatic OpenAPI docs
- **PostgreSQL**: Relational database with schema `library_catalog`
- **SQLAlchemy 2.x**: ORM with sync sessions
- **Pydantic v2**: Request/response validation and serialization
- **pytest**: Test framework with SQLite fixtures

## Business Logic

- **Loan period**: Configurable via `LOAN_DAYS` (default 14 days)
- **Member limits**: Max 5 active loans (configurable via `MAX_ACTIVE_LOANS`)
- **Hold queue**: FIFO by `placed_at` timestamp, auto-fulfilled on book return
- **Availability**: `available_copies = total_copies - active_loans`
- **Overdue**: Computed as `due_at < NOW() AND returned_at IS NULL`
- **Concurrency**: Database constraints prevent double-checkout of same book

## Error Codes

| Status | Condition | Example |
|--------|-----------|---------|
| 401 | Missing/invalid auth | No `X-Member-Key` header |
| 403 | Access denied | Member trying to return someone else's loan |
| 404 | Resource not found | Book/loan/hold ID doesn't exist |
| 409 | Business rule conflict | Book unavailable, duplicate ISBN, active loans on delete |
| 422 | Validation error | Invalid request body format |