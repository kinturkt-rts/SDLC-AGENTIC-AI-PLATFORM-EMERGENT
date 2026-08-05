---
name: developer-agent
description: >
  Implements FastAPI backend services under target-apps/ from PRD, design doc, database-agent
  handoff, and scraped research. Use when working on developer-agent, target-apps code, or
  scaffolding new services. Patterns A (in-memory), B (Postgres CRUD), B+ (Postgres+Bedrock),
  B++ (local RAG with pgvector), C (FastAPI + Streamlit UI).
---

# Developer Agent

## Pipeline position

```
product-agent → architect-agent → web-crawler-agent → database-agent → developer-agent
    ↓
 qa-agent / devops-agent
```

## What this agent produces

Working FastAPI application under `target-apps/<service>/` with:
- All routes from design **API surface** implemented and registered in `main.py`
- Pydantic v2 request/response schemas matching ORM column names exactly
- SQLAlchemy models mirroring database-agent SQL exactly (same column names, types, ENUMs, UUIDs)
- Baseline pytest suite that passes (`pytest tests/ -q`)
- `README.md` with repo-root paths, Terminal 1/2 blocks (Streamlit), endpoint table, curl examples
- `## Context handoff` JSON block consumed by qa-agent and devops-agent

## What it does NOT produce

| Artifact | Owner |
|---|---|
| `.env` (real secrets) | Human — copy `.env.example` → `.env` locally |
| `tests/test_qa_*.py`, `QA_REPORT.md` | qa-agent |
| `db/sql/` migrations | database-agent — read-only for developer-agent |
| Dockerfile, docker-compose, Terraform | devops-agent |
| Frontend (React, Next.js) | Phase 2 |

`dev_write_file` enforces these — it actively blocks `.env`, `QA_REPORT.md`, `test_qa_*.py`.

## When to run this agent

Run after `database-agent` has written `db/sql/` and its `agents/pipeline/<app>.database-handoff.md`. Run again only if:
- Design doc changes (new endpoint, changed schema)
- Handoff produced incomplete routes (check pre-handoff checklist in DEVELOPER_SYS_PROMPT)

Do NOT run to fix small bugs — edit the generated file directly in that case.

## Pattern decision tree

```
Design data model says...
  ├─ No persistence / in-memory only  →  Pattern A  (app/main.py + app/models.py)
  ├─ Postgres, no LLM                 →  Pattern B  (full app/ layout)
  ├─ Postgres + Bedrock/LLM           →  Pattern B+ (B + app/services/)
  ├─ Postgres + pgvector + RAG        →  Pattern B++ (B+ + ingestion + retriever)
  └─ Any above + "streamlit" in stack →  Pattern C  (backend/ + streamlit_app/)
```

State the chosen pattern and cite the design heading before writing any file.

## Stack selection

| Design tech stack says | Generated stack |
|---|---|
| Python / FastAPI | Python 3.12+, FastAPI, Pydantic v2, uvicorn |
| Node / Express | Node 20+, Express/Fastify, TypeScript |
| React / Next.js | React 18+, TypeScript (Phase 2 only) |
| Go | Go 1.22+ as specified |
| Silent / ambiguous | Default Python/FastAPI; add to `open_questions` |

## Context keys consumed

| Key | Set by | What it gives developer-agent |
|---|---|---|
| `prdPath` | product-agent | Acceptance criteria, user stories, NFRs |
| `designDocPath` | architect-agent | Tech stack, API surface, Auth rules, file layout |
| `databaseHandoffPath` | database-agent (auto-discovered) | Schema, DSN, ORM notes, seed UUIDs |
| `preferredSqlPath` / `dbOutputDir` | database-agent | Path to `db/sql/` migrations |
| `scrapedMarkdownPaths` | web-crawler-agent (auto-discovered) | External API docs, competitor research |
| `dbBackend` | inferred from disk | `postgres`, `mongodb`, `postgres+mongodb` |
| `architectSummary` | architect-agent | Short orientation |
| `jiraKey` | orchestrator | Traceability in docstrings/README |

## Artifacts generated (Pattern B example)

```
target-apps/<service>/
  app/
    __init__.py
    main.py            # FastAPI app, lifespan, all include_router() calls
    config.py          # pydantic-settings get_settings() with @lru_cache
    database.py        # dialect-guarded engine, SessionLocal, get_db()
    dependencies.py    # require_api_key() and/or get_current_user() per design Rules
    models/
      __init__.py
      pg_types.py      # pg_enum(), pg_uuid_column() — Postgres/SQLite ORM parity
      <entity>.py      # SQLAlchemy ORM — 1:1 with db/sql/ column names and types
    routers/
      __init__.py
      health.py        # GET /health → {"status": "ok"}
      <domain>.py      # one file per API domain
    services/          # Pattern B+ / B++ only — omit for plain CRUD
      __init__.py
      bedrock_client.py
      prompts.py
      ingestion.py     # B++ only
      pgvector_retriever.py  # B++ only
  schemas/
    __init__.py
    <domain>.py        # Pydantic v2 Create/Update/Out — field names match ORM columns
  tests/
    conftest.py        # DATABASE_URL override BEFORE app import; get_db override; fixtures
    test_health.py
    test_<domain>.py
  requirements.txt     # only packages actually imported
  .env.example         # every env var config.py reads; placeholder values only
  .gitignore           # .env and .venv/ at minimum
  README.md            # Local dev + Deployment (AWS dev) sections
```

## Most common failure modes (why you re-run)

| Symptom | Root cause | Pre-handoff check |
|---|---|---|
| `ImportError` on `uvicorn` start | Missing `__init__.py` in `models/`, `routers/`, `schemas/` | All dirs have `__init__.py` |
| `ImportError: circular import` | `schemas/` imports from `models/` or vice versa | Import direction: routers→schemas+models; models→pg_types only |
| Route returns 200 instead of 201 | `status_code=` missing from `@router.post()` decorator | Every POST has `status_code=201` on decorator |
| Route not in Swagger | Router file not registered with `app.include_router()` in `main.py` | Count routers == count include_router calls |
| 422 on valid request | Schema field name doesn't match ORM column name (snake_case mismatch) | Schema fields identical to ORM column names |
| 422 on list endpoint | Response shape doesn't match API surface (page vs array) | Match design: `{items,total,limit,offset}` OR `list[Schema]` |
| 500 on RDS but pytest green | ENUM/UUID ORM mismatch; wrong driver; missing sslmode | psycopg[binary], pg_enum/pg_uuid_column, `?sslmode=require` |
| Wrong auth on routes | JWT added when Rules say API-key only (or vice versa) | Auth deps match design Rules exactly |
| `pytest` passes but `uvicorn` 500s | `Settings()` called at module level; env not loaded | `get_settings()` with `@lru_cache` only |
| `pytest` fails to import app | `DATABASE_URL` env not set before `from app.main import app` | conftest.py sets env vars as first lines |
| Bedrock test calls real AWS | Mock patched at definition site not import site | Patch `app.routers.<module>.get_bedrock_client` |
| Missing routes | Agent wrote router but forgot some endpoints | Route manifest written before any file |

## Run commands

```bash
# Pipeline default (auto-loads context from agents/pipeline/<app>.context.json)
python agents/developer-agent/developer_agent.py

# With explicit context file
python agents/developer-agent/developer_agent.py \
  --context-file agents/pipeline/<app>.context.json

# Ad-hoc with task override
python agents/developer-agent/developer_agent.py \
  --target-app my-service \
  --task "Add POST /export endpoint returning CSV from sessions table"

# With chain-of-thought reasoning streamed to stderr
DEVELOPER_AGENT_THINKING=true \
python agents/developer-agent/developer_agent.py

# A2A server mode
python agents/developer-agent/developer_agent.py --serve-a2a
```

## Environment variables

```bash
CODING_MODEL_ID=us.anthropic.claude-opus-4-6         # default model
DEVELOPER_AGENT_MAX_TOKENS=32768                     # prevents mid-file truncation
BEDROCK_READ_TIMEOUT=600                             # seconds; long for large codegen
DEVELOPER_TARGET_APP=my-service                      # overrides targetApp in context
DEVELOPER_AGENT_THINKING=true                        # stream reasoning to stderr
DEVELOPER_AGENT_THINKING_BUDGET=8192                 # adaptive thinking token budget
AWS_REGION=us-east-2
AWS_PROFILE=eks-admin-user                           # for Bedrock + RDS SSO
```

## Verifying the output worked (before moving to qa-agent)

Run these checks after every developer-agent run:

```bash
cd target-apps/<service>

# 1. Install and start
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in real values

# 2. Run tests — must pass with zero failures
pytest tests/ -q

# 3. Start server
uvicorn app.main:app --reload --port 8000

# 4. Check Swagger — all routes from design API surface must appear
open http://localhost:8000/docs

# 5. Smoke test health
curl http://localhost:8000/health
# Expected: {"status":"ok"}

# 6. Postgres apps: RDS smoke test (pytest uses SQLite — this proves RDS works)
curl http://localhost:8000/<list-route>
# Expected: page object or list per API surface — NOT a 500 or 422
# API-key apps: curl -H "X-API-Key: $API_KEY" http://localhost:8000/<protected-route>
```

If any step fails, that's a developer-agent gap — re-run with `--task "Fix: <symptom>"` 
or patch the specific file manually (faster for single-file fixes).

## Template reference (`target-apps/_template/`)

The `_template` directory is a **reference few-shot** for Postgres-backed FastAPI services.
It is NOT auto-copied — the agent reads it and adapts. Key files:

| Template file | What it shows |
|---|---|
| `app/database.py` | Dialect-guarded engine (skips pool_size on SQLite), `get_db()` with yield |
| `app/config.py` | `get_settings()` with `@lru_cache`; reads PORT, DATABASE_URL, POSTGRES_SCHEMA |
| `app/models/pg_types.py` | UUID and ENUM SQLAlchemy type helpers for Postgres/SQLite parity |
| `app/services/bedrock_client.py` | `invoke_text()` + `invoke_embed()` wrapping boto3 |
| `app/services/ingestion.py` | PDF parse → chunk → embed → INSERT document_chunks (B++ pattern) |
| `app/services/pgvector_retriever.py` | Cosine similarity search over document_chunks |
| `db/reference/rag_pgvector_reference.sql` | Expected pgvector schema for B++ apps |
| `tests/conftest.py` | SQLite override before app import; dependency override; reset_db fixture |

## Common ORM pitfall (M2M + POSTGRES_SCHEMA)

Never write `relationship(..., secondary="junction_table")` as a string.
With `MetaData(schema=POSTGRES_SCHEMA)` the table is registered as `schema.junction_table`,
so a bare name fails on the first ORM query (often login) with `InvalidRequestError`.
Always define `junction = Table(...)` and pass `secondary=junction` (the object).
`dev_validate_app` hard-fails string `secondary=` values.

## Downstream handoff JSON keys

After run, agent appends `## Context handoff` to stdout with:

```json
{
  "writtenFiles": ["target-apps/my-svc/app/main.py", "..."],
  "targetApp": "my-svc",
  "runCommandLocal": "cd target-apps/my-svc && uvicorn app.main:app --reload --port 8000",
  "testCommand": "cd target-apps/my-svc && pytest tests/ -q",
  "userSetupCommand": "cd target-apps/my-svc && cp .env.example .env",
  "envVarsRequired": ["DATABASE_URL", "API_KEY", "..."],
  "deploymentHandoff": {
    "targetEnvironment": "aws-dev",
    "port": 8000,
    "healthCheckPath": "/health",
    "containerEntrypoint": "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}",
    "envVarNames": ["PORT", "DATABASE_URL", "..."],
    "secretsSource": "AWS Secrets Manager, SSM, or ECS task IAM role",
    "dockerReady": true,
    "notes": "devops-agent owns Dockerfile, CI/CD, and AWS deploy"
  },
  "dbBackend": "postgres",
  "jiraKey": "SAAP-42",
  "openQuestions": []
}
```

`localhost` in README/curl = local dev only. `deploymentHandoff` gives devops-agent everything
it needs for Docker/ECS without developer-agent generating a Dockerfile.