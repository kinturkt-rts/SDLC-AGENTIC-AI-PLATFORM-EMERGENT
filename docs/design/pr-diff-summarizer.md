# AI PR Diff Summarizer — Solution Design

## 1. Summary
FastAPI service that processes pull request diffs using AWS Bedrock Claude to generate summaries and risk scores. Stores analysis history in Postgres with API key authentication. TBD: specific API key values and diff size limits.

## 2. Stack
| Layer | Technology |
|-------|------------|
| API | FastAPI + Uvicorn |
| Database | PostgreSQL |
| AI/ML | AWS Bedrock Claude Sonnet |
| Authentication | API Key (X-API-Key header) |
| UI | Streamlit (demo) |

## 3. Data model
| Table / collection | Columns (name type PK/FK UNIQUE) | Indexes / constraints |
|--------------------|----------------------------------|------------------------|
| reviews | id UUID PK, submitted_at TIMESTAMP, title TEXT, diff_text TEXT, file_count INT, lines_added INT, lines_removed INT, summary TEXT, risk_score INT, risk_band risk_band_enum, model_id TEXT, created_by TEXT | idx_submitted_at, idx_risk_band, idx_created_by |
| api_keys | key_hash VARCHAR(255) PK, name TEXT, created_at TIMESTAMP, is_active BOOLEAN | UNIQUE(key_hash) |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | /reviews | `{"title": str, "diff_text": str}` | `{"id": str, "summary": str, "risk_score": int, "risk_band": str}` | Auth required |
| GET | /reviews | Query: `limit=20, offset=0, risk_band=Optional[str]` | `{"items": [...], "total": int}` | Auth required |
| GET | /reviews/{id} | - | `{"id": str, "submitted_at": str, "title": str, "summary": str, "risk_score": int, "risk_band": str}` | Auth required |
| GET | /stats | - | `{"last_30_days": {"low": int, "medium": int, "high": int}, "avg_risk_score": float}` | Auth required |
| GET | /health | - | `{"status": "healthy"}` | No auth |

## 5. Rules
- Auth: API key validation via X-API-Key header on all endpoints except /health
- Risk calculation: LLM base score + heuristics (+15 migrations/, +10 secrets, -10 if <30 lines), clamped 0-100
- Risk bands: 0-30=low, 31-70=medium, 71-100=high
- Audit: Log all API requests with timestamp, endpoint, user (created_by), response time
- Idempotency: Reviews identified by UUID, no duplicate prevention
- Input limits: 10MB max diff_text size, 500 char max title
- Bedrock: Retry 3x with exponential backoff on failures

## 6. DB delivery
1. Migration order: `001_create_reviews_table.sql`, `002_create_api_keys_table.sql`, `003_add_indexes.sql`
2. Seed data: Insert demo API key hash, 3-5 sample reviews with varying risk bands
3. Enums: CREATE TYPE risk_band_enum AS ENUM ('low', 'medium', 'high')
