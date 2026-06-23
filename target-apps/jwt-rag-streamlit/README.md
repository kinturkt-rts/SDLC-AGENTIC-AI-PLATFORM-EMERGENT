# JWT RAG Streamlit - Policy RAG Portal

Internal policy RAG portal enabling JWT-authenticated employees to upload PDFs and query policy documents via natural language chat. Built with FastAPI backend, PostgreSQL + pgvector for semantic search, Amazon Bedrock for LLM responses, and Streamlit UI.

## Features

- **JWT Authentication**: Role-based access control (admin, contributor, viewer)
- **Document Management**: PDF upload with automatic ingestion and chunking  
- **RAG Chat**: Natural language queries with citations and confidence scoring
- **Collection Organization**: Group documents by policy categories
- **Audit Logging**: Comprehensive tracking of user actions
- **Streamlit UI**: Role-gated tabs for chat, documents, and member management

## Architecture

- **Backend**: FastAPI with JWT Bearer authentication
- **Database**: PostgreSQL with pgvector extension for vector similarity search
- **LLM**: Amazon Bedrock Claude Sonnet v4 for natural language responses
- **Embeddings**: Amazon Bedrock Titan Embed v2 (1024 dimensions)
- **UI**: Streamlit calling API over HTTP
- **Storage**: Local filesystem for PDF documents

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL with pgvector extension
- AWS credentials with Bedrock access
- Git Bash (Windows) or terminal (Mac/Linux)

### Setup

1. **Clone and navigate**:
   ```bash
   cd target-apps/jwt-rag-streamlit
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv .venv
   
   # Windows (Git Bash)
   source .venv/Scripts/activate
   
   # Mac/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment configuration**:
   ```bash
   cp .env.example .env
   # Edit .env with your actual values - every line needs the variable name
   ```

   **Critical**: In `.env`, use full `KEY=value` format:
   ```
   DATABASE_URL=postgresql+psycopg://username:password@host:port/database?sslmode=require
   JWT_SECRET_KEY=your-secret-key-change-in-production
   AWS_REGION=us-east-2
   ```
   
   Don't paste bare URLs - include the `DATABASE_URL=` prefix.

5. **Database setup**:
   The database schema and seed data are already applied to RDS. Your `.env` should point to:
   ```
   DATABASE_URL=postgresql+psycopg://username:password@agenticaidbinstance.c1u0cggiolxp.us-east-2.rds.amazonaws.com:5432/sdlc_agentic_ai?sslmode=require
   POSTGRES_SCHEMA=jwt_rag_streamlit
   ```

### Running the Application

**Terminal 1 - API Server**:
```bash
# From target-apps/jwt-rag-streamlit/
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Streamlit UI**:
```bash
# From target-apps/jwt-rag-streamlit/
cd ui
streamlit run streamlit_app.py --server.port 8501
```

### Access Points

- **API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **Streamlit UI**: http://localhost:8501
- **Health Check**: http://localhost:8000/health

### Demo Credentials

The seed data includes test users with password "PolicyPortal2024!":

| Email | Role | Password | Access |
|-------|------|----------|--------|
| admin@company.com | admin | PolicyPortal2024! | Full system access |
| hr.manager@company.com | contributor | PolicyPortal2024! | Upload documents + view |
| jane.employee@company.com | viewer | PolicyPortal2024! | View and chat only |

## API Usage

### Authentication
```bash
# Login to get JWT token
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@company.com", "password": "PolicyPortal2024!"}'

# Use token in subsequent requests
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/collections
```

### Document Upload
```bash
curl -X POST http://localhost:8000/collections/1/documents \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@policy.pdf" \
  -F "title=Company Policy 2024"
```

### Chat Query
```bash
curl -X POST http://localhost:8000/collections/1/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the vacation policy?"}'
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | *(required)* | PostgreSQL connection string |
| `POSTGRES_SCHEMA` | `jwt_rag_streamlit` | Database schema name |
| `JWT_SECRET_KEY` | *(required)* | Secret key for JWT signing |
| `JWT_EXPIRES_MINUTES` | `60` | Token expiration time |
| `AWS_REGION` | `us-east-2` | AWS region for Bedrock |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-20250514-v1:0` | LLM model |
| `BEDROCK_EMBED_MODEL_ID` | `amazon.titan-embed-text-v2:0` | Embedding model |
| `CONFIDENCE_THRESHOLD` | `0.25` | Minimum confidence for answers |
| `PDF_STORAGE_DIR` | `./uploaded_pdfs` | Local PDF storage path |

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_auth.py -v
```

## Project Structure

```
jwt-rag-streamlit/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Environment configuration
│   ├── database.py          # SQLAlchemy setup
│   ├── startup_checks.py    # Runtime validation
│   ├── dependencies.py      # Auth and dependency injection
│   ├── models/              # SQLAlchemy ORM models
│   ├── routers/             # API endpoints
│   └── services/            # Business logic
├── ui/
│   ├── streamlit_app.py     # Streamlit UI application
│   └── requirements.txt     # UI-specific dependencies
├── schemas/                 # Pydantic request/response models
├── tests/                   # Test suite
├── requirements.txt         # Python dependencies
├── .env.example             # Environment template
└── README.md
```

## Troubleshooting

### Database Connection Issues
- Verify `DATABASE_URL` format includes `postgresql+psycopg://`
- Ensure RDS security group allows connections from your IP
- Check that pgvector extension is installed: `CREATE EXTENSION vector;`

### Bedrock Access Issues
- Verify AWS credentials are configured (`aws configure` or IAM role)
- Ensure Bedrock model access is enabled in AWS console
- Check `AWS_REGION` matches your Bedrock model availability

### Streamlit UI Issues
- Ensure API is running on port 8000 before starting Streamlit
- Check `API_BASE_URL` in Streamlit environment matches API server
- Verify JWT tokens are not expired (60 minute default)

### PDF Upload Issues
- Only PDF files are supported
- Maximum file size is 10MB
- Ensure `PDF_STORAGE_DIR` is writable
- Check disk space for document storage

### RDS Smoke Test
```bash
# Test database connectivity
curl http://localhost:8000/health

# Should return: {"status":"ok","checks":{"api":"ok","database":"ok"}}
```

## Security Notes

- JWT tokens expire in 60 minutes by default
- All passwords are hashed with bcrypt
- API requires Bearer token authentication for all protected endpoints
- Audit logging tracks all user actions with timestamps and IP addresses
- Collection-based access control prevents unauthorized document access

## Support

For technical issues:
1. Check health endpoint: `GET /health`
2. Review application logs for error details
3. Verify environment configuration matches `.env.example`
4. Ensure all required services (PostgreSQL, Bedrock) are accessible