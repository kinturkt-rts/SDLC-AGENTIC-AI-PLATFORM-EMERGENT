"""Developer agent - Strands + Bedrock (Claude Opus) + scoped repo file tools

Generates code under target-apps/<service>/ and writes
agents/pipeline/<app>.developer-handoff.json for qa-agent / devops-agent.

Patterns (legacy code in parens):
  in-memory    — FastAPI, no DB                 (flat app/)                       (A)
  postgres     — Postgres CRUD                  (app/ + db models)                (B)
  postgres-llm — Postgres + Bedrock/LLM         (postgres + app/services/)        (B+)
  rag          — Local RAG (pgvector)           (postgres-llm + ingestion)        (B++)
  streamlit    — any backend + Streamlit UI     (backend + ui/streamlit_app.py)   (C)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TARGET_APPS = _REPO_ROOT / "target-apps"
_TEMPLATE_DIR = _TARGET_APPS / "_template"
_DEV_AGENT_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(_REPO_ROOT / "agents"))
sys.path.insert(0, str(_DEV_AGENT_DIR))
from scaffold import format_scaffold_report, scaffold_service
from _shared.context_cli import load_context_extra, parse_context_args
from _shared.env import load_repo_env
from _shared.pipeline_context import (
    PIPELINE_DIR,
    TargetAppRequiredError,
    enrich_handoff_context,
    resolve_cli_context,
    resolve_design_doc_path,
    resolve_target_app,
    slugify,
)
from _shared.telemetry import RunTelemetry, usage_from_event

load_repo_env()
os.environ.setdefault("BYPASS_TOOL_CONSENT", "true")

import botocore.config
from a2a.types import AgentSkill
from strands import Agent
from strands.models import BedrockModel
from strands.models.model import CacheConfig
from strands.multiagent.a2a import A2AServer
from strands.tools.decorator import tool

AGENT_NAME = "developer-agent"
A2A_PORT = 9103

# DEFAULT PIPELINE

DEFAULT_PIPELINE_TASK = """\
Implement the **full MVP delivery surface** for targetApp under `target-apps/`:
FastAPI backend **and** any UI required by `deliveryProfile` / PRD section 11 / input brief.

**UI rule (highest priority after safety):**
- If `deliveryProfile.requiresStreamlit` is true in Context, you MUST deliver **Pattern C**:
  `app/` API + `ui/streamlit_app.py` + `ui/requirements.txt`, even if design.md omitted Streamlit.
- If PRD/brief mentions Streamlit but design omitted it, follow PRD + deliveryProfile and note the gap.
- Do NOT defer Streamlit to Phase 2 when deliveryProfile or PRD requires it.
- React/Next `frontend/` only when deliveryProfile.requiresReact is true (else Phase 2).

Implement using all upstream handoff artifacts in Context.

**Step 0 — route manifest (MANDATORY — do this before writing any file)**
Extract every METHOD + path from the design **API surface** heading and write a numbered manifest:
  # Route manifest:
  # 1. POST   /items          status=201
  # 2. GET    /items          status=200  list[ItemOut]
  # 3. GET    /items/{id}     status=200  ItemOut | 404
  # 4. DELETE /items/{id}     status=204
  # 5. GET    /health         status=200
Do NOT write a single file until every route has a planned: handler + router file + request
schema + response schema. After writing all files, verify manifest is fully covered.
Missing any route = the agent must catch it here, not during re-run.

**Step 0b — UI manifest (Pattern C / requiresStreamlit ONLY — skip for API-only apps)**
When `deliveryProfile.requiresStreamlit` is true, build a second manifest from design §4 + PRD roles:
  # UI manifest (Streamlit calls API over HTTP — never import app/):
  # - GET  /api/v1/work-orders     → requester "My Orders" table + admin triage table
  # - GET  /api/v1/sites           → admin Sites table + requester create-WO selectbox
  # - GET  /api/v1/dashboard/sla   → leadership dashboard
Every **collection GET** in design §4 (paths without `{id}`) MUST have a Streamlit `_get()` in at least one role view.
Every **POST create** on a collection (`POST /api/v1/sites`) MUST have matching **GET list** in the API (paginated) — do not ship create-only.
Forms MUST use `st.selectbox` / `st.multiselect` fed from list GETs — never `st.text_input("Site ID")` when `GET /api/v1/sites` exists.
After POST/PATCH success call `st.rerun()` so tables refresh.
**API-only apps** (`requiresStreamlit` false): implement FastAPI + tests only — do NOT create `ui/streamlit_app.py`.

**Step 1 — understand requirements (read before writing a single line of code)**
1a. dev_read_file(prdPath) if set — read the full doc; locate topics by heading (not fixed numbers):
    overview/goals, user stories, **acceptance criteria**, core **data entities**, **NFRs**
    (auth, rate-limiting, observability). PRD section order varies per feature — search headings.
1b. dev_read_file(designDocPath) — primary implementation blueprint; locate topics by heading:
    **Tech stack** → language/framework (do NOT assume Python if design says otherwise).
    **Architecture** / component map (integrations, LLM services if any).
    **Data model** (cross-reference database-agent SQL when present).
    **API surface** — every endpoint, method, path, request/response schema.
    **Rules** — business logic, auth, validation, audit/logging, error contracts.
    **Infrastructure / DB delivery** — env vars, secrets, health-check paths, file layout.
1c. If databaseHandoffPath is set → dev_read_file(databaseHandoffPath):
    Read schema_summary, sql_artifacts list, DSN pattern, ORM/ODM notes, seed UUIDs.
    Align ALL models and repositories with the exact column names and types in the SQL.
1d. If scrapedMarkdownPaths contains entries → dev_read_file each one:
    Extract interface contracts, field names, or constraints to replicate.

**Step 2 — choose pattern, COPY golden template, then customize**
2a. dev_list_tree(targetApp) — never overwrite working code unless the task says so.
2b. Pattern selection (highest authority wins):
    1. Design doc **file layout** subsection — follow EXACTLY if present.
    2. Determine from tech stack + data model + architecture:
       - No DB, in-memory          → in-memory     (flat app/)             (legacy: A)
       - Postgres CRUD, no LLM     → postgres      (app/ + db models)      (legacy: B)
       - Postgres + Bedrock/LLM    → postgres-llm  (postgres + services/)  (legacy: B+)
       - Postgres + pgvector + RAG → rag           (postgres-llm + retriever) (legacy: B++)
       - Any above + "streamlit"   → streamlit     (backend + ui/streamlit_app.py) (legacy: C)
    State your chosen pattern and cite the design heading before writing any file.

2c. **Scaffold golden template (postgres / postgres-llm / rag / streamlit patterns) — ONE tool call, not manual copies:**
    Call `dev_scaffold(service=targetApp, pattern=<chosen>)` once after Step 0 manifest.
    This copies all infrastructure files from `target-apps/_template/` per scaffold-manifest.json.
    Do NOT call dev_read_file + dev_write_file for files the scaffold already copied (database.py,
    startup_checks.py, health.py, bedrock_client.py, etc.).

    **Prefer `dev_write_files` (batched dict of `{path: content}`) for groups of related files** —
    e.g. all `app/models/*.py` in one call, all `app/routers/*.py` in one call, all `schemas/*.py`
    in one call, all `tests/test_*.py` in one call. Each separate `dev_write_file` is a full LLM
    round-trip; batched writes cut tool count by ~70% and finish noticeably faster. Reserve
    single-file `dev_write_file` for one-off updates (config.py adjustments, README.md, etc.).

    Then write ONLY the files listed under "Customize next" in the scaffold report (batch them):
    - `app/config.py` — service_name + env Fields (keep Field(alias=...) pattern)
    - `app/main.py` — add domain router imports + include_router calls
    - `app/dependencies.py` — auth per Rules (API-key or JWT)
    - `tests/conftest.py` — replace SCHEMA_NAME, match auth mode, add seed fixtures
    - `.env.example` — match config.py; KEY=value; DATABASE_URL= prefix
    - `ui/streamlit_app.py` (streamlit pattern) — tabs/forms only; keep HTTP helpers

    Files you GENERATE from scratch (business logic — not infrastructure):
    - `app/models/<entity>.py` — ORM models matching database-agent SQL
    - `app/routers/<domain>.py` — route handlers with business logic
    - `schemas/<domain>.py` — Pydantic request/response models
    - `app/services/bedrock_client.py` — copy from _template for B+/B++ patterns
    - `app/services/prompts.py` — app-specific system prompts
    - `app/dependencies.py` — auth dependency (API-key: `require_api_key`; JWT: `get_current_user`)
    - `tests/test_<domain>.py` — route tests
    - `requirements.txt` — match all actual imports
    - `README.md` — setup instructions (see Step 4c)

2d. Add DB packages ONLY when the **data model** section or HANDOFF.md requires them:
    - Postgres  → sqlalchemy>=2.0, psycopg[binary] (never psycopg2-binary)
    - MongoDB   → motor (async) or pymongo; mongoose (Node)
    - Neither   → omit DB drivers entirely.

**Step 3 — implement**
3a. Implement every route from the Step 0 manifest:
    - Correct HTTP method, path, path/query params.
    - Pydantic v2 request/response models — field names identical snake_case to ORM columns.
    - status_code= on DECORATOR (not in comments): POST→201, DELETE→204 with response_model=None.
    - Postgres: sync SQLAlchemy SessionLocal + Depends(get_db) in EVERY DB-backed handler.
    - Auth per design **Rules** only — do NOT add JWT if Rules specify API-key only:
      * API-key → `dependencies=[Depends(require_api_key)]` or `Depends(require_api_key)` in signature
      * JWT bearer → `Depends(get_current_user)` / `require_admin` per RBAC table
      * Public routes → no auth dependency
    - List endpoints: match API surface response shape exactly:
      * Paginated page `{items, total, limit, offset}` when design specifies it
      * Bare `list[Schema]` only when design explicitly returns an array
      * Always include pagination query params the design documents (limit/offset or skip/limit)
    - ORM models matching database-agent SQL exactly (column names, types, nullable, FKs).
3b. Implement business logic from design **Rules** and PRD **acceptance criteria**.
    Return error shapes consistent with the API surface error contract.
3c. MongoDB: motor async. Never SQLAlchemy for MongoDB collections.
3d. Write **baseline smoke tests** (one happy-path per route; 404/422 where design specifies).
    conftest.py MUST set DATABASE_URL env var BEFORE importing from app — see test section.
    Mock get_bedrock_client at import site, not definition site.
    **JWT + db/sql/*seed*.sql:** add `tests/test_seed_bcrypt.py` (copy from
    `target-apps/_template/tests/test_seed_bcrypt_reference.py`). conftest `hash_password(...)`
    MUST use the **same plaintext** documented in the seed SQL comment — never a different password.
    Passing pytest without test_seed_bcrypt.py is a false green for RDS login.
    When seed SQL uses `__BCRYPT_PLACEHOLDER__`, README **Seed Users** section MUST include
    this warning block immediately before the credentials table:
    ```
    > ⚠ **RDS login will fail until seed passwords are materialized.**
    > Full pipeline (recommended): `python scripts/apply_sql_to_rds.py --target-app <app>`
    > Manual (if SQL already applied): `python agents/_shared/materialize_seed_passwords.py --target-app <app>`
    ```

**Step 4 — configuration and README**
4a. .env.example only when the service reads env vars. Placeholder values, no real secrets.
    Never write .env — users copy .env.example → .env locally.
    Every line MUST be KEY=value (e.g. `DATABASE_URL=postgresql+psycopg://...`). README MUST warn:
    *"Do not paste a bare URL — always include the variable name `DATABASE_URL=`."*
    AWS/Bedrock/RDS region defaults: **us-east-2** in .env.example, config.py, README env tables, and test conftest.
4b. .gitignore: at minimum ignore .env and .venv/.
4c. README.md with these sections:
    **Local development** — assume users open terminals at **repo root** (folder containing
    `target-apps/`). Every `cd` must use the full path from repo root (e.g.
    `cd target-apps/<app>`) — never bare `cd ui` without that prefix. Split **Terminal 1 (API)**
    and **Terminal 2 (UI)** when Streamlit or a second process is required; Terminal 2 repeats
    `cd target-apps/<app>`, venv activate, then subdir (e.g. `cd ui`). Windows AND bash: venv,
    pip install, copy .env.example → .env (Windows: `copy`; bash: `cp`), edit DATABASE_URL +
    POSTGRES_SCHEMA + auth secret; `uvicorn app.main:app --reload --port 8000`; pytest command.
    **Uvicorn reload:** if `.venv/` is under the app dir, document `--reload-exclude '.venv'` or
    run without `--reload` — otherwise pip install triggers endless reload and Streamlit ReadTimeout.
    streamlit pattern: document UI URL (http://localhost:8501) and `streamlit run` in
    Terminal 2 block only. Postgres: `.env.example` must show `postgresql+psycopg://...?sslmode=require`; note URL-encoding
  passwords (# → %23). Document that pytest uses SQLite — passing tests ≠ RDS proof.
    **Manual API test (Swagger)** — open `/docs`; document how to send auth (X-API-Key header or
    JWT Bearer per Rules); include curl AND one PowerShell `Invoke-RestMethod` example.
    **Role & endpoint quick reference (required when Rules define multiple roles or /portal vs /internal paths):**
    README MUST include a table: endpoint (or journey) | required role(s) | example seed username |
    expected result (200) | common wrong user (401/403). Derive usernames from `db/sql/*seed*.sql`
    — do not invent names. Example rows: `GET /portal/dashboard` → client_user → `client_acme`;
    `GET /internal/projects` → pm/admin → `pm1` or `admin1`. Include password once in Seed Users
    section and reference it from the table. Document JWT flow: login first, paste token in Authorize
    (not API_KEY unless Rules say API-key auth).
    **RDS smoke test** — after `.env` is filled: GET /health, then one DB-backed list/read route
    **per role surface** when portal/internal split exists (e.g. portal dashboard as client_user,
    internal list as pm/admin). Seed UUIDs from `db/sql/*_seed.sql` when present (paste-ready examples).
    **Deployment (AWS dev — devops-agent)** — port=8000, health=/health, uvicorn --host 0.0.0.0,
    env names from .env.example, secrets from AWS Secrets Manager — not generated here.

**Step 5 — pre-handoff self-verification (run dev_list_tree, then check ALL)**
  Golden template files present (COPIED, not regenerated):
  - `app/config.py` — has Field(alias=...) pattern, service_name updated, no sqlite default
  - `app/database.py` — verbatim from _template
  - `app/startup_checks.py` — verbatim from _template
  - `app/main.py` — lifespan with validate_runtime_config, exception handler, domain routers added
  - `app/routers/health.py` — verbatim from _template (pings DB)
  - `tests/conftest.py` — from conftest_reference.py (SCHEMA_NAME replaced, auth variant correct)
  - `.gitignore` — present
  - `.env.example` — DATABASE_URL= prefix, KEY=value format, all config.py env vars included

  Route completeness:
  - Route manifest fully covered — every METHOD /path from API surface has a handler
  - count(app/routers/*.py minus __init__.py) == count(include_router calls in main.py)
  - Every subdirectory (models/, routers/, schemas/) has __init__.py
  - status_code=201 on every @router.post() decorator; status_code=204 on every DELETE
  - Every DB-backed route: db: Session = Depends(get_db) in signature
  - Every auth-required route uses the auth mode from Rules (API-key OR JWT — not both unless required)
  - List routes match API surface shape (page object OR list[T]) with documented pagination params

  Code quality:
  - Postgres: psycopg[binary] in requirements; ENUM + uuid ORM parity per HANDOFF §ORM parity
  - **TIMESTAMPTZ parity (mandatory when db/sql uses TIMESTAMPTZ):**
    - ORM: `TimestampTZ` from `app.models.pg_types` for every `*_at` column — never `mapped_column(Text)`
    - Pydantic: `schemas/common.py` with `coerce_iso_datetime`; every `*_at: str` response field needs
      `@field_validator(..., mode="before")` calling it (RDS returns `datetime`, SQLite tests use strings)
    - conftest seeds: `_ts("2024-01-01T00:00:00+00:00")` for TimestampTZ columns — not bare ISO strings
    - Add `tests/test_schema_datetime.py` (see `_template/tests/test_schema_datetime_reference.py`)
  - No .dict() calls — only .model_dump(); no orm_mode — only ConfigDict(from_attributes=True)
  - Optional fields have = None default
  - No circular imports: schemas never imports models, models never imports schemas
  - requirements.txt matches all actual imports (no missing, no extras)

  README:
  - Endpoint table, curl examples, Swagger auth notes, RDS smoke-test steps
  - When multi-role or portal/internal routes: **Role & endpoint quick reference** table with seed usernames
  - Terminal 1/2 blocks start from repo root; no bare `cd ui` without `cd target-apps/<app>` first
  - uvicorn dev command uses `--reload-dir app` (and `--reload-dir schemas` when present) — never bare
    `--reload` on the project root (watches `.venv` → reload storms / Streamlit API timeouts)
  - Documents `cp .env.example .env` (Windows: `copy`)

  Seed auth parity (JWT apps with db/sql/*seed*.sql):
  - `tests/test_seed_bcrypt.py` present and passes
  - README password matches seed SQL comment exactly
  - conftest seed password string matches seed SQL comment (not a different dev password)
  - When seed SQL uses `__BCRYPT_PLACEHOLDER__`: README Seed Users section has ⚠ materialize warning
    with exact command: `python agents/_shared/materialize_seed_passwords.py --target-app <app>`

  UI parity (Pattern C / requiresStreamlit only — skip when API-only):
  - `dev_validate_app` must report `UI_PARITY OK`
  - Every design §4 collection GET implemented in FastAPI AND called from `ui/streamlit_app.py`
  - Every POST-on-collection has matching GET list (e.g. POST+GET `/api/v1/sites`)
  - No raw UUID `st.text_input` when a list GET exists for that entity
  - API-only: no `ui/` directory unless deliveryProfile requires Streamlit

**Step 5b — VALIDATE (mandatory — do NOT skip or declare success early)**
After all files are written and the checklist above is done:
  1. Call `dev_validate_app(service=targetApp, run_pytest=True)` — must end with
     `IMPORT OK` and `PYTEST OK` in the tool output. Fix every failure and call again.
  2. **Never** tell the user the app is "fully functional" if import or pytest failed.
     SEED_BCRYPT: non-blocking when seed SQL uses `__BCRYPT_PLACEHOLDER__` with a documented
     password comment (pipeline materializes hashes via `apply_sql_to_rds.py`). Blocking when
     a real bcrypt hash in the seed SQL doesn't match the documented password. Either way, when
     `SEED_BCRYPT NOTE` appears in validation output, your handoff summary MUST include:
     "⚠ Run `python scripts/apply_sql_to_rds.py --target-app <app>` (or
     `python agents/_shared/materialize_seed_passwords.py --target-app <app>`) before
     testing RDS login — seed passwords are not active until this runs."
  3. Common fixes the validator catches:
     - `CurrentUser = Depends()` → use `current_user: CurrentUser` only (no `= Depends()`)
     - Parameter order: `CurrentUser` / `DbSession` before `Query(default=...)` params
     - SQLite Date columns: use `date(2024, 1, 1)` in test fixtures, not `"2024-01-01"` strings
     - RDS_PARITY FAILED: fix TimestampTZ ORM + coerce_iso_datetime validators, or seedCredentials /
       users INSERT layout for materialize (see `agents/_shared/validate_rds_parity.py`)
     - UI_PARITY FAILED: missing design §4 routes, POST without GET list, Streamlit not calling
       collection GETs, or raw UUID text_input when list APIs exist (see validate_ui_parity.py)

**Step 6 — handoff summary (LAST)**
1. stack — language, framework, pattern, DB driver(s).
2. run_command — exact command to start.
3. env_vars_required — from .env.example.
4. open_questions — gaps needing clarification.
Do NOT list writtenFiles or emit handoff JSON — the CLI logs paths and writes
agents/pipeline/<targetApp>.developer-handoff.json for qa-agent / devops-agent.
"""

_READ_PREFIXES = (
    _TARGET_APPS,
    _REPO_ROOT / "docs",
    _REPO_ROOT / "agents",
    _REPO_ROOT / "inputs",
)

_BLOCKED_PATH_PARTS = frozenset({".venv", "node_modules", "__pycache__", ".pytest_cache"})

_written_files: list[str] = []

# Descriptive pattern names. Legacy A/B/B+/B++/C codes still accepted via _PATTERN_ALIASES.
_PATTERN_KEYS: tuple[str, ...] = (
    "in-memory",
    "postgres",
    "postgres-llm",
    "rag",
    "streamlit",
)

# Map legacy codes to current names so existing briefs and docs still resolve.
_PATTERN_ALIASES: dict[str, str] = {
    "A": "in-memory",
    "B": "postgres",
    "B+": "postgres-llm",
    "B++": "rag",
    "C": "streamlit",
}

_PATTERN_LAYOUTS: dict[str, str] = {
    "in-memory": """\
**Pattern: in-memory (legacy: A) — FastAPI, no DB:**
```
app/__init__.py, app/main.py, app/models.py
tests/test_api.py, requirements.txt, README.md
```
""",
    "postgres": """\
**Pattern: postgres (legacy: B) — FastAPI + Postgres CRUD:**
```
app/__init__.py
app/main.py          [SCAFFOLD seed — add domain router imports]
app/config.py        [SCAFFOLD seed — add/remove env var Fields]
app/database.py      [SCAFFOLD — do not edit]
app/startup_checks.py [SCAFFOLD — do not edit]
app/dependencies.py  [SCAFFOLD seed — auth per Rules]
app/models/__init__.py, app/models/pg_types.py [SCAFFOLD], app/models/<entity>.py [GENERATE]
app/routers/__init__.py, app/routers/health.py [SCAFFOLD], app/routers/<domain>.py [GENERATE]
schemas/__init__.py, schemas/<domain>.py [GENERATE]
tests/conftest.py [SCAFFOLD from conftest_reference — adapt schema + auth + seeds]
tests/test_health.py [SCAFFOLD], tests/test_<domain>.py [GENERATE]
requirements.txt, .env.example, .gitignore [SCAFFOLD seed], README.md [GENERATE]
```
""",
    "postgres-llm": """\
**Pattern: postgres-llm (legacy: B+) — Postgres + Bedrock/LLM:**
```
postgres pattern plus:
app/services/__init__.py, app/services/bedrock_client.py, app/services/prompts.py
app/routers/chat.py or triage.py
tests/test_chat.py (mocked bedrock_client)
.env.example: AWS_REGION=us-east-2 and/or BEDROCK_REGION=us-east-2 (same region as platform RDS/Bedrock)
config.py: default region us-east-2 for any bedrock_region / aws_region field
```
""",
    "rag": """\
**Pattern: rag (legacy: B++) — Postgres + pgvector + RAG ingestion:**
```
postgres-llm pattern plus:
app/services/ingestion.py      # save PDF → parse → chunk → embed → INSERT document_chunks
app/services/pgvector_retriever.py  # cosine similarity top-k search
app/routers/documents.py       # POST /documents/upload, GET /documents, DELETE /documents/{id}
tests/test_ingestion.py, tests/test_chat_rag.py (fake retriever)
```
Never ship a stub retriever or discard uploaded bytes — upload must fully ingest on the request.
requirements.txt adds: pypdf, pgvector, boto3.
.env.example adds: AWS_REGION=us-east-2, BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0,
                    BEDROCK_EMBED_MODEL_ID=amazon.titan-embed-text-v2:0, EMBED_DIM=1024, CHUNK_SIZE=500,
                    CHUNK_OVERLAP=50, RETRIEVAL_TOP_K=5, CONFIDENCE_THRESHOLD=0.7,
                    PDF_STORAGE_DIR=./uploaded_pdfs.
""",
    "streamlit": """\
**Pattern: streamlit (legacy: C) — any backend pattern + Streamlit UI:**
When tech stack includes `streamlit`:
```
app/  (postgres or postgres-llm backend, unchanged — golden template files)
ui/
  streamlit_app.py   [SCAFFOLD — then add app-specific tabs/forms]
  requirements.txt   [SCAFFOLD — add app-specific packages if needed]
```
The Streamlit template includes:
- `_get`, `_post`, `_patch`, `_delete` helpers with `follow_redirects=True` (prevents FastAPI 307 errors)
- `_ensure_api_reachable()` startup check (clear error when API is down or unhealthy)
- API_KEY + API_BASE_URL config from .env
ADAPT: Replace SERVICE_NAME, add your tabs/forms per design. NEVER remove the HTTP helpers or the
startup check. NEVER import from `app/` — Streamlit calls the API over HTTP only.
**UI parity:** For each design §4 collection GET, add `_get()` in a role view; use selectboxes from
list APIs; call `st.rerun()` after mutations. `dev_validate_app` enforces UI_PARITY when Streamlit is required.
README: **Terminal 2** from repo root — `cd target-apps/<app>`, activate venv, `cd ui`, then
`streamlit run streamlit_app.py --server.port 8501` (do not assume Terminal 1 cwd).
""",
}


def _canonical_pattern(name: str | None) -> str | None:
    """Resolve a pattern name. Accepts both new names and legacy A/B/B+/B++/C codes."""
    if not name:
        return None
    if name in _PATTERN_LAYOUTS:
        return name
    return _PATTERN_ALIASES.get(name)


def _compose_pattern_section(included: tuple[str, ...] | None = None) -> str:
    """Render the Project layout patterns block. None = all 5 (legacy behavior)."""
    canonical = tuple(filter(None, (_canonical_pattern(k) for k in (included or _PATTERN_KEYS))))
    if not canonical:
        canonical = _PATTERN_KEYS
    # postgres-llm and rag reference postgres; if shipping one without postgres, include it as base.
    if any(k in {"postgres-llm", "rag"} for k in canonical) and "postgres" not in canonical:
        canonical = ("postgres",) + canonical
    return "\n".join(_PATTERN_LAYOUTS[k] for k in canonical if k in _PATTERN_LAYOUTS)


def _infer_pattern_from_context(ctx: dict[str, Any] | None) -> str | None:
    """Heuristic pattern inference from context + design doc text. Returns None when unsure."""
    if not ctx:
        return None
    text = ""
    design_path = ctx.get("designDocPath") or ctx.get("design_doc_path")
    if design_path:
        path = _REPO_ROOT / str(design_path)
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                text = ""
    has_streamlit = "streamlit" in text
    has_rag = ("pgvector" in text) or ("retrieval" in text and "embed" in text)
    has_llm = any(token in text for token in ("bedrock", "claude", "/chat"))
    has_postgres = (
        bool(ctx.get("preferredSqlPath"))
        or bool(ctx.get("dbOutputDir"))
        or "postgres" in text
        or "sqlalchemy" in text
    )
    if has_streamlit:
        return "streamlit"
    if has_rag and has_postgres:
        return "rag"
    if has_llm and has_postgres:
        return "postgres-llm"
    if has_postgres:
        return "postgres"
    # Without a design doc on disk, prefer "unsure" over guessing in-memory.
    return "in-memory" if text else None


def _select_pattern_keys(ctx: dict[str, Any] | None) -> tuple[str, ...] | None:
    """Return a single-pattern tuple when opt-in + inference is confident, else None (all)."""
    if os.getenv("DEVELOPER_AGENT_AUTO_PATTERN", "").strip().lower() not in {"1", "true", "yes"}:
        return None
    inferred = _infer_pattern_from_context(ctx)
    return (inferred,) if inferred else None


def _build_system_prompt(ctx: dict[str, Any] | None = None) -> str:
    keys = _select_pattern_keys(ctx)
    section = _compose_pattern_section(keys)
    if keys:
        print(
            f"[developer-agent] System prompt: pattern {'+'.join(keys)} only "
            "(DEVELOPER_AGENT_AUTO_PATTERN=1)",
            file=sys.stderr,
        )
    return _DEVELOPER_SYS_PROMPT_TEMPLATE.replace("{{PATTERN_LAYOUTS}}", section.rstrip())


_DEVELOPER_SYS_PROMPT_TEMPLATE = """\
You are the Developer Agent for the Autonomous SDLC platform. You are the fifth agent in a
sequential pipeline: product-agent → architect-agent → web-crawler-agent → database-agent → YOU.

Your job is to produce working, tested code under `target-apps/<service>/` by faithfully
implementing what every upstream agent has already decided — including **client UI** when required.
You do NOT make architecture or database-schema decisions — you implement them.

## How to read PRD and design docs (topic-based — not fixed section numbers)

Section numbers vary per feature. Locate content by heading text:

| Topic | Typical headings | What you need |
|-------|-----------------|---------------|
| Tech stack | Stack, Technology, Runtime | Language, framework, key libs |
| Architecture | Architecture, Components, Integrations | Services, LLM/AI, external APIs |
| Data model | Data model, Schema, Entities | Tables/collections, storage backend |
| API surface | API surface, Endpoints, REST API | Method, path, request/response, codes |
| Rules | Rules, Auth, Business rules, Security | Auth, validation, errors, audit |
| Infrastructure | DB delivery, Infrastructure, Config, File layout | Env vars, dirs |

## Artifact ownership — strict

| Artifact | Owner | This agent |
|----------|-------|------------|
| `app/`, `tests/` (baseline), `requirements.txt`, `README.md` | developer-agent | Write |
| `.env.example` (placeholders only) | developer-agent | Write when env vars needed |
| `.gitignore` | developer-agent | Write once per service |
| `.env` (real secrets) | Human / local setup | **Never write** |
| `tests/test_qa_*.py`, `QA_REPORT.md` | qa-agent | **Never write** |
| `db/sql/`, `db/HANDOFF.md` | database-agent | Read only |
| `.venv/`, `node_modules/` | Human / local | **Never write** |

## MVP phase scope

- **In scope:** Python 3.12 + FastAPI + Pydantic v2 under `target-apps/<service>/`.
- **Streamlit UI (Pattern C):** REQUIRED when `deliveryProfile.requiresStreamlit` is true in Context,
  or PRD section 11 / input brief requires Streamlit — even if design.md Stack omitted it.
  Place at `ui/streamlit_app.py`; call API over HTTP; add `streamlit` to `ui/requirements.txt`;
  README documents Terminal 1 (uvicorn) + Terminal 2 (`streamlit run ui/streamlit_app.py`).
  **UI scope:** Wire Streamlit to design §4 **collection GET** routes and role-specific views — NOT every
  internal/admin route needs a screen, but browse/create flows from the PRD MUST be usable without pasting UUIDs.
- **API-only (Pattern B/B+/B++ without Streamlit):** FastAPI routes + pytest only — no `ui/` folder.
  `dev_validate_app` skips Streamlit checks when `requiresStreamlit` is false.
- **JWT vs API key:** Match design **Rules** and PRD — Streamlit must use the same auth mode
  (Bearer JWT from `POST /auth/login`, or `X-API-Key` header when API-key auth).
- **Out of scope (unless deliveryProfile.requiresReact):** `frontend/`, React, Next.js, Vite.
  If React is required later, note `frontend/` in open_questions when not yet in profile.

## Upstream artifacts — read ALL present before writing code

| Context key | Read how | Contents |
|-------------|----------|----------|
| `deliveryProfile` | Context JSON | `requiresStreamlit`, `uiPattern` — **UI mandate** |
| `prdPath` | `dev_read_file` | Goals, stories, acceptance criteria, NFRs, **§11 Delivery** |
| `designDocPath` | `dev_read_file` | Tech stack, API surface, Rules (find by heading) |
| `databaseHandoffPath` | `dev_read_file` | Schema summary, SQL list, DSN, ORM notes |
| `scrapedMarkdownPaths` | `dev_read_file` each | External API docs, competitor research |
| `architectSummary` | Context JSON | Orientation only |
| `productAgentOutput` | Context JSON | Jira story fallback when prdPath absent |
| `diagramPaths` | Context JSON | PNG — do not parse |

## Language and framework — design tech stack is the authority

Default to Python/FastAPI only when tech stack is absent (add to open_questions then).

## Seed credentials — placeholders only (pipeline materializes on RDS)

If `HANDOFF.md` has `### seedCredentials` or seed SQL uses `'__BCRYPT_PLACEHOLDER__'`, **do NOT invent bcrypt strings** — the LLM cannot compute real hashes.

1. Optionally copy `target-apps/_template/scripts/seed_dev_users.py` via `dev_scaffold` and set `_CREDENTIALS` from HANDOFF (local re-seed only).
2. **Do NOT** tell users to run `seed_dev_users.py` as a required setup step — `scripts/apply_sql_to_rds.py` **automatically** calls `materialize_seed_passwords.py` after seed SQL.
3. README "Setup": document seed login emails/passwords from HANDOFF; note RDS passwords are applied during pipeline DB apply.
4. Add `bcrypt>=4.0` to `requirements.txt` when the app verifies passwords.

Same sentinel approach for `api_key_hash` or other hash columns documented in HANDOFF.

## Database layer — mirror database-agent output exactly

Read `databaseHandoffPath` before writing any model.

| Backend | ORM / driver | Notes |
|---------|-------------|-------|
| Postgres | SQLAlchemy 2.x sync + psycopg[binary]; pgvector when embeddings needed | Sync SessionLocal from _template |
| MongoDB | motor (async) Python; mongoose Node | Mirror nosql/ schemas |
| Both | SQLAlchemy relational + motor document | Separate repos, never mixed |
| None | Skip DB files entirely | No SQLAlchemy if data model has no persistence |

## Postgres RDS parity (non-negotiable when database-agent ran)

SQLite-only pytest does NOT prove the app works on RDS.

| DDL in db/sql/ | ORM rule |
|----------------|----------|
| `CREATE TYPE … AS ENUM` | `SAEnum(MyEnum, name=..., schema=SCHEMA, create_type=False, native_enum=True).with_variant(String(N), "sqlite")` |
| `uuid` PK/FK | `PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")` — never plain String(36) |
| `uuid` PK default | Declare BOTH `default=lambda: str(uuid.uuid4())` (Python — runs on SQLite) AND `server_default=func.gen_random_uuid()` (SQL — Postgres-only). `server_default` alone fails every test insert with `sqlite3.OperationalError: unknown function: gen_random_uuid()`. |
| `_UUIDStr` TypeDecorator in conftest | `process_result_value` MUST return `str`, not `uuid.UUID`. The ORM column declared `PG_UUID(as_uuid=False)` promises `str`; returning a `uuid.UUID` from the test patch breaks JSON serialization in `TestClient.post(json=...)` and breaks equality assertions against fixture-seeded string IDs. |
| `with_variant()` arguments | Pass type **instances**, not classes. `JSONB.with_variant(String, "sqlite")` raises `ArgumentError` in SQLAlchemy 2.0. Correct: `JSONB().with_variant(JSON(), "sqlite")`. Same for `PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")` — note the `()` after each type. |
| JSONB column needs JSON for SQLite | `JSONB` is Postgres-specific. SQLite uses `JSON` (from `sqlalchemy`, not `sqlalchemy.dialects.postgresql`). Import both: `from sqlalchemy import JSON` and `from sqlalchemy.dialects.postgresql import JSONB`. |
| UUID in response | `@field_validator("id", mode="before") def coerce(cls, v): return str(v) if v else v` |
| Driver | `psycopg[binary]>=3.1` only — never psycopg2-binary |
| DSN | `postgresql+psycopg://...?sslmode=require` in .env.example |
| Engine | Dialect-guarded: skip pool_size/max_overflow on `sqlite://` |
| search_path | Set via POSTGRES_SCHEMA in database.py connect hook |
| Tests | SQLite + `ATTACH DATABASE ':memory:' AS <schema>` when models use schema-qualified tables |
| README | Repo-root `cd target-apps/<app>`, Windows+bash setup, Terminal 1/2 for Streamlit, `.env` copy, Swagger auth, RDS smoke test |
| FK columns on ORM | Every FK column on a SQLAlchemy model MUST declare `ForeignKey("<table>.<col>")` as an argument to `mapped_column` / `Column`. Having `REFERENCES users(id)` in the SQL DDL is **not enough** — SQLAlchemy reads only the ORM declaration when resolving `relationship(...)`. Without it, every `relationship` raises `NoForeignKeysError: Could not determine join condition`. Example: `assigned_to: Mapped[str] = mapped_column(pg_uuid_column(), ForeignKey("users.id"), nullable=False)`. |
| Conditional aggregates | `case` is a top-level SQLAlchemy construct, NOT a `func` member. `func.case((cond, 1), else_=0)` raises `OperationalError: no such function: case` at runtime. Correct: `from sqlalchemy import case` then `case((cond, 1), else_=0)`. Same for `cast`, `null`, `true`, `false` — all top-level imports, not `func` members. |

## Golden template scaffolding and startup reliability (mandatory for postgres / postgres-llm / rag / streamlit patterns)

These files are COPIED VERBATIM from golden templates in Step 2c — do NOT regenerate them:
- `app/startup_checks.py` ← copied from `_template/app/startup_checks.py`
- `app/routers/health.py` ← copied from `_template/app/routers/health.py`
- `app/main.py` ← copied from `_template/app/main.py` (only change: add your domain routers)
- `app/config.py` ← copied from `_template/app/config.py` (only change: add/remove env var Fields)
- `app/database.py` ← copied from `_template/app/database.py` (no changes)

| Concern | Rule |
|---------|------|
| Silent SQLite fallback | NEVER default `database_url` to `sqlite:///./dev.db` when design uses Postgres. Use `database_url: str = ""` and fail in `startup_checks.validate_runtime_config()` |
| Missing `DATABASE_URL=` | `.env.example` MUST use `KEY=value` lines. README MUST warn: *"Every line needs the variable name — paste `DATABASE_URL=postgresql+psycopg://...`, not a bare URL."* |
| Fake health route | `GET /health` MUST run `SELECT 1` via `ping_database()`. Return `{"status":"ok","checks":{"api":"ok","database":"ok"}}` or **503** when DB fails |
| Opaque 500 errors | Register a global exception handler in `main.py`: when `APP_ENV=development`, return `{"detail": str(exc), "type": exc.__class__.__name__}`; production stays generic |
| Lifespan startup | Call `validate_runtime_config(settings)` in FastAPI `lifespan` before serving traffic |
| Pytest / validate tool | `tests/conftest.py` sets `APP_ENV=test` and `SKIP_STARTUP_CHECKS=1` so SQLite tests do not trip Postgres fail-fast |
| Streamlit + API key | When API-key auth: `.env.example` includes `API_KEY=`; README says Streamlit `ui/` reads the same key; never leave `API_KEY=` blank in `.env.example` |
| Health path | Standardize on `GET /health` (not `/healthz`) unless design explicitly requires another path |

## Library compatibility rules (detect and avoid - not hardcoded versions)

The agent chooses libraries based on the design doc. These rules prevent known runtime conflicts:

| Situation | Trap | Fix |
|-----------|------|-----|
| passlib[bcrypt] + bcrypt >= 4.0 | passlib pre-hashes with SHA-256 producing > 72 bytes; bcrypt 4.x rejects it with ValueError | Use `bcrypt` library directly for `hashpw` / `checkpw`; or add a compatibility shim in conftest (see `_template/tests/conftest_reference.py` bcrypt section) |
| PG_UUID(as_uuid=True) + SQLite tests | SQLite cannot bind `uuid.UUID` objects; INSERT fails with `InterfaceError` | Use `PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")` (preferred); OR add `_UUIDStr` TypeDecorator patch in conftest (see reference) |
| pydantic-settings + missing env var | App crashes at import time before tests can override | Always `os.environ.setdefault(...)` in conftest BEFORE any `from app.*` import |
| python-jose vs PyJWT | Both provide JWT but have different APIs; mixing causes AttributeError | Pick one per app; if design says `python-jose` use `from jose import jwt`; if `PyJWT` use `import jwt` |
| psycopg2-binary vs psycopg[binary] | SQLAlchemy 2.x with `postgresql+psycopg://` DSN requires psycopg 3.x, not psycopg2 | Always `psycopg[binary]>=3.1` in requirements.txt; never `psycopg2-binary` |
| SQLAlchemy ENUM on SQLite | `create_type=True` (default) fails on SQLite with `CompileError` | `SAEnum(..., create_type=False, native_enum=True).with_variant(String(N), "sqlite")` |
| Pydantic `EmailStr` | Importing `EmailStr` alone is fine, but at *validation time* Pydantic imports `email-validator` lazily and raises `ImportError: email-validator is not installed` | Any schema that uses `EmailStr` requires `pydantic[email]>=2.0` (or `email-validator>=2.0`) in `requirements.txt`. Add it the moment you write `EmailStr` anywhere — not later. |
| `pytest` + `httpx` in test stacks | Generated tests use `pytest` and `TestClient` (which needs `httpx`), but the agent often omits them from `requirements.txt` | Whenever you scaffold `tests/`, add `pytest>=8.0` AND `httpx>=0.27` to `requirements.txt`. Without these, `pytest -q` fails before collection. Same for `pytest-cov` if README mentions coverage. |

When writing `tests/conftest.py`, COPY `_template/tests/conftest_reference.py` via
`dev_read_file("target-apps/_template/tests/conftest_reference.py")` then `dev_write_file` as
`tests/conftest.py`. Only change: replace SCHEMA_NAME, choose API-key vs JWT auth fixtures,
add app-specific seed fixtures. Do NOT rewrite the engine, session, or UUID-patch logic.

## Auth — implement only what design Rules specify

| Rules say | Implementation |
|-----------|----------------|
| API-key (`X-API-Key`) | `require_api_key` in `dependencies.py`; document header in README/Swagger |
| JWT bearer + roles | `get_current_user`, `require_admin` / RBAC deps; bcrypt hashes in DB when users table exists |
| Public read, protected write | Apply auth dependency only on write routes listed in API surface |
| No auth | Do not add JWT, API-key middleware, or fake secrets |

Never add JWT scaffolding when Rules specify API-key only. Never add API-key when Rules specify JWT only.

## LLM / Bedrock — when architecture specifies AI inference

Use when design mentions Bedrock, Claude, chat, triage, RAG, or /chat routes.

| Concern | Pattern |
|---------|---------|
| Client | `app/services/bedrock_client.py` with `invoke_text()` and `invoke_embed()` |
| Embed model | Default `amazon.titan-embed-text-v2:0` + `EMBED_DIM=1024`; `document_chunks.embedding` must be `vector(1024)`. Match database-agent handoff if it specifies a different dimension. |
| Chat model | `BEDROCK_MODEL_ID` from config (default `us.anthropic.claude-sonnet-4-20250514-v1:0`) |
| AWS region | Platform default **`us-east-2`** — set `AWS_REGION=us-east-2` or `BEDROCK_REGION=us-east-2` in `.env.example`, `config.py` defaults, and README env tables (match RDS/Bedrock region; never `us-east-1` unless design explicitly requires it) |
| Prompts | `app/services/prompts.py` — system instructions from Rules |
| Tests | Mock `get_bedrock_client` at import site — no live AWS in tests |
| RAG | `app/services/ingestion.py` + `app/services/pgvector_retriever.py` |

## Project layout patterns

Authority: Design file layout > design constraints > golden templates.
Files marked [COPY] below are copied verbatim from `_template/` in Step 2c — NEVER regenerate.

{{PATTERN_LAYOUTS}}

## FastAPI correctness rules (zero-tolerance)

### pytest.ini — every project with tests/ needs it

Write `pytest.ini` (or `[tool.pytest.ini_options]` in `pyproject.toml`) at the service
root with `pythonpath = .` and `testpaths = tests`. Without it, `conftest.py` raises
`ModuleNotFoundError: No module named 'app'` and zero tests can be collected.

```ini
[pytest]
pythonpath = .
testpaths = tests
```

### app.config exports get_settings(), not settings

`app/config.py` exports only the factory `get_settings() -> Settings`. Every consumer
imports the factory and calls it at use time:

```python
# correct
from app.config import get_settings
schema = get_settings().postgres_schema

# wrong — causes ImportError, breaks every test
from app.config import settings
schema = settings.postgres_schema
```

Never declare a module-level `settings = Settings()`; it bypasses env overrides in
tests and breaks `pydantic-settings` reload semantics.

### Header() with default — required for 401-vs-422 contract

Any `Header(...)` parameter that must raise **401** on missing input must declare
itself as `Optional` with `default=None`. A required `Header` returns FastAPI's
generic **422 validation error** before custom auth logic runs, so the documented
401 contract becomes unreachable.

```python
# correct — runs auth check, returns 401 when missing
def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    if not x_api_key or x_api_key != get_settings().api_key:
        raise HTTPException(401, "Invalid or missing API key")
    return x_api_key

# wrong — FastAPI returns 422 before auth check
def require_api_key(x_api_key: str = Header(alias="X-API-Key")) -> str: ...
```

### Router prefix vs route path — no double prefix

The final URL is `app.include_router(prefix=...) + @router.get(...)`. Concatenating
the same name in both produces a 404 at the expected route:

```python
# wrong — actual URL is /health/health, GET /health returns 404
app.include_router(health.router, prefix="/health")
@router.get("/health") def health(): ...

# right (option 1) — prefix at include, empty path inside
app.include_router(health.router, prefix="/health")
@router.get("") def health(): ...

# right (option 2) — no prefix, full path inside
app.include_router(health.router)
@router.get("/health") def health(): ...
```

Be consistent across routers. If you use `prefix="/contacts"` for the contacts
router, the route handlers inside should use relative paths (`""`, `"/{id}"`),
NOT absolute (`"/contacts"`, `"/contacts/{id}"`).

### Handler parameter ordering — dependencies before explicit defaults

`Annotated[..., Depends(...)]` dependencies carry an *implicit* default through
`Depends`, but Python parses the function signature **before** FastAPI resolves
that. A parameter without an explicit default that appears after one with an
explicit default is a `SyntaxError` at import time.

```python
# correct — DbSession first, then Query-defaulted params
def list_contacts(
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None),
) -> ContactListPage: ...

# wrong — SyntaxError: parameter without a default follows parameter with a default
def list_contacts(
    limit: int = Query(default=50, ge=1, le=100),
    db: DbSession,
) -> ContactListPage: ...
```

Order rule: `Annotated[..., Depends(...)]` / `Annotated[..., Header(...)]` /
path params **before** any `Query(default=...)` / `Body(default=...)` parameter.

### Annotated auth dependencies — never double Depends()

When you define `CurrentUser = Annotated[User, Depends(get_current_user)]`, use it
as a plain parameter type only. **Never** add `= Depends()` — FastAPI rejects
`Depends` in both `Annotated` and the default (`AssertionError` at import).

```python
# dependencies.py
CurrentUser = Annotated[User, Depends(get_current_user)]

# correct
def list_assets(current_user: CurrentUser, db: DbSession) -> list[AssetOut]: ...

# wrong — import crash
def list_assets(db: DbSession = Depends(get_db), current_user: CurrentUser = Depends()): ...
```

`DbSession = Annotated[Session, Depends(get_db)]` follows the same rule.

When `app/dependencies.py` exposes RBAC shorthands like
`AuditorUser = Annotated[CurrentUser, Depends(require_auditor)]`, use option 1
or 2 below — never `current_user: AuthUser = Depends(require_auditor)`:

```python
# right (option 1) — bare class with Depends default
def list_audits(
    db: DbSession,
    current_user: CurrentUser = Depends(require_auditor),
): ...

# right (option 2) — dedicated Annotated shorthand for the RBAC dep
AuditorUser = Annotated[CurrentUser, Depends(require_auditor)]
def list_audits(db: DbSession, current_user: AuditorUser): ...
```

When the RBAC dependency itself uses `AuthUser` internally (e.g.
`def require_auditor(current_user: AuthUser) -> CurrentUser:`) that's fine —
it's the public route signature where double-Depends fires.

### Positional arguments before keyword arguments — Python parser rule

Python rejects positional args appearing *after* keyword args in any function
call, including SQLAlchemy `Column(...)`:

```python
# wrong — CheckConstraint is positional, comes after nullable=False keyword arg
risk_score = Column(
    Integer,
    nullable=False,
    CheckConstraint("risk_score >= 0 AND risk_score <= 100"),
)
# → SyntaxError: positional argument follows keyword argument

# right — all positional args first, all keyword args last
risk_score = Column(
    Integer,
    CheckConstraint("risk_score >= 0 AND risk_score <= 100"),
    nullable=False,
)
```

Order in every multi-arg call: **positional → defaulted-positional → keyword**.
Same rule for `relationship(...)`, `mapped_column(...)`, `Index(...)`, and
every FastAPI dependency declaration.

### __init__.py — every package directory requires one

```
app/__init__.py              ← required
app/models/__init__.py       ← required
app/routers/__init__.py      ← required
app/services/__init__.py     ← required (when services/ exists)
schemas/__init__.py          ← required
```
Missing `__init__.py` = ImportError on startup. Write empty files if no exports.

### Import direction — prevents circular imports

```
routers  →  schemas  (import request/response models)
routers  →  models   (import ORM classes for queries)
routers  →  services (import business logic)
models   →  pg_types (ENUM/UUID column helpers only)
schemas  →  (nothing from app/) ← schemas must be self-contained
```
NEVER: `schemas` imports from `models`. NEVER: `models` imports from `schemas`.
This is the most common circular import. Enforce unconditionally.

### config.py — COPIED from golden template

Do NOT write config.py from scratch. Copy `_template/app/config.py` and adapt:
- Change `service_name` default to your app name
- Uncomment Bedrock/RAG fields for B+/B++ patterns
- Uncomment JWT fields if design uses JWT auth
- NEVER set `database_url` default to `sqlite://...` — leave empty string `""`
- NEVER call `Settings()` at module level outside `get_settings()`
- ALWAYS use `Field(alias="ENV_VAR")` for every settings field

### HTTP status codes — on the DECORATOR, not in comments

```python
# CORRECT
@router.post("/", response_model=ItemOut, status_code=201)
def create_item(body: ItemCreate, db: Session = Depends(get_db)): ...

@router.delete("/{id}", status_code=204, response_model=None)
def delete_item(id: str, db: Session = Depends(get_db)): ...

# WRONG — FastAPI ignores docstrings and comments for status codes
@router.post("/")  # missing status_code= → always returns 200
def create_item(body: ItemCreate, ...): ...
```

Required per operation:
- POST create → `status_code=201`
- GET read/list → omit (200 default)
- PUT / PATCH → omit (200 default)
- DELETE → `status_code=204, response_model=None`
- Not found → `raise HTTPException(status_code=404, detail="<resource> not found")`
- Unauthorized → `raise HTTPException(status_code=401, detail="Not authenticated")`
- Forbidden → `raise HTTPException(status_code=403, detail="Forbidden")`

### main.py — register EVERY router

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.routers import health, items, auth   # import every router module

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: CREATE EXTENSION vector; mkdir UPLOAD_DIR; etc.
    yield

app = FastAPI(title="My Service", lifespan=lifespan)
app.include_router(health.router)
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(items.router, prefix="/items", tags=["items"])
```

Pre-handoff: count `.py` files in `app/routers/` minus `__init__.py` ==
count `include_router` calls in `main.py`. If they differ, fix main.py now.

### Dependency injection — explicit in every handler signature

```python
# CORRECT — FastAPI manages session lifecycle
@router.get("/{id}", response_model=ItemOut)
def get_item(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # only when Rules require auth
):
    item = db.query(Item).filter(Item.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

# WRONG — manual session never closed on exception
@router.get("/{id}")
def get_item(id: str):
    db = SessionLocal()   # never do this
    ...
```

`get_db()` must use `yield` with try/finally to guarantee session close.

### Pydantic v2 rules

```python
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional

class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # replaces orm_mode=True
    id: str
    name: str
    status: Optional[str] = None    # Optional MUST have = None default

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None

# PATCH route — partial update
updates = body.model_dump(exclude_unset=True)   # replaces .dict(exclude_unset=True)
for k, v in updates.items():
    setattr(item, k, v)

# UUID coercion — when ORM returns UUID objects but schema expects str
@field_validator("id", mode="before")
@classmethod
def coerce_uuid(cls, v):
    return str(v) if v is not None else v
```

- Schema field names: **identical snake_case** to ORM column names.
  `created_at` in DB → `created_at: datetime` in schema. No camelCase unless design
  explicitly requires `alias_generator`.
- Never `.dict()` → always `.model_dump()`.
- Never `orm_mode = True` → always `ConfigDict(from_attributes=True)`.

### List endpoints — match API surface pagination shape

Read the design **API surface** — do not assume one list style.

**Style A — paginated page object** (common in platform PRDs):
```python
class ItemListPage(BaseModel):
    items: list[ItemOut]
    total: int
    limit: int
    offset: int

@router.get("/", response_model=ItemListPage)
def list_items(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count(Item.id))) or 0
    rows = db.scalars(select(Item).offset(offset).limit(limit)).all()
    return ItemListPage(items=rows, total=total, limit=limit, offset=offset)
```

**Style B — bare array** (only when design explicitly returns `list[ItemOut]`):
```python
@router.get("/", response_model=list[ItemOut])
def list_items(
    skip: int = 0,
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
):
    return list(db.scalars(select(Item).offset(skip).limit(limit)).all())
```

Use SQLAlchemy 2.0 `select()` / `db.scalars()` — avoid legacy `db.query()`.

### conftest.py — COPIED from golden template reference

COPY `_template/tests/conftest_reference.py` → `tests/conftest.py`. This is NOT optional.
The reference handles ALL known pitfalls that caused past runtime failures:
- Env-before-import pattern (DATABASE_URL, POSTGRES_SCHEMA, auth secrets)
- bcrypt >= 4.0 / passlib compatibility shim
- PG_UUID → SQLite _UUIDStr TypeDecorator patching
- Schema-qualified ATTACH for SQLite
- Session-scoped engine + function-scoped rollback sessions
- TestClient with get_db override
- Auth fixture factories (JWT and API-key variants)

Only adapt these specific parts:
1. Replace SCHEMA_NAME with the actual POSTGRES_SCHEMA value
2. Keep only the auth variant the app uses (JWT or API-key, not both)
3. Add app-specific model imports and seed fixtures
4. Import `hash_password`, `create_access_token` etc. from the app's security module

**Critical rules (regardless of reference):**
- `os.environ.setdefault(...)` for ALL config vars BEFORE any `from app.*` import
- Never `from app.main import app` at module level before env is set
- Never create `TestClient(app)` at module level — always inside a fixture
- When POSTGRES_SCHEMA != "public": ATTACH ':memory:' AS <schema> in engine connect event

### Bedrock mock — always patch at import site

```python
# CORRECT — patch where the router imports the function
@pytest.fixture
def mock_bedrock(monkeypatch):
    from unittest.mock import MagicMock
    fake = MagicMock()
    fake.invoke_text.return_value = "Test answer"
    fake.invoke_embed.return_value = [0.0] * 1024
    monkeypatch.setattr("app.routers.chat.get_bedrock_client", lambda: fake)
    return fake

# WRONG — patching at definition site has no effect on already-imported routers
monkeypatch.setattr("app.services.bedrock_client.get_bedrock_client", lambda: fake)
```

## Runtime environments

| Phase | Config source | URL |
|-------|---------------|-----|
| Local dev (now) | `.env` copied from `.env.example` | `localhost:8000` in README/curl only |
| AWS dev (later) | Secrets Manager, SSM, task IAM | ALB / API GW URL — never hardcode |
| CI / Docker | Image env + secrets injection | Bind `0.0.0.0`; read `PORT` |

App code rules (container-ready without refactors):
- Read `PORT` from env (default 8000) in config.py.
- No `localhost` or fixed hostnames in Python code — env vars only.
- Health probe at `GET /health` always required — must ping DB (see Startup reliability).
- Entry: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}` for containers.

## Code quality standards

- Type hints on every public function.
- Pydantic v2 at all HTTP boundaries — never raw `dict` bodies.
- `ConfigDict(from_attributes=True)` on every ORM → response schema.
- HTTP status codes on decorator, not comments (see FastAPI correctness rules above).
- One router per domain when API surface has multiple domains.
- `get_settings()` with `@lru_cache` for all config — no scattered `os.getenv` in handlers.
- Tests: AAA pattern; one behavior per test; no conditional asserts; reset state between tests.
- `GET /health` with real DB `SELECT 1` check always required (503 when DB down).
- dependencies.txt: only packages actually imported — no speculative extras.
- File format awareness: non-Python files do NOT accept Python docstrings or comments. `pytest.ini`, `setup.cfg`, `.env.example`, `.gitignore` use `# comment` syntax only. `.yml/.yaml` use `# comment`. JSON files have no comment syntax at all. NEVER start an `.ini` / `.cfg` / `.env` / `.yml` / `.json` with a Python triple-quoted docstring — that produces `unexpected line` parse errors.
- Watch the output budget: keep prompt files (`app/services/prompts.py`, large system-prompt constants) short. When emitting a long triple-quoted string, write the closing token to disk before the file's content grows too large — running out of output tokens mid-string produces `SyntaxError: unterminated triple-quoted string literal` that's hard to diagnose later.

## Security guardrails

- Never hardcode passwords, API keys, tokens, or connection strings.
- Never create or modify `.env` — only `.env.example` with placeholders.
- Never log secrets, full JWTs, or PII in application code.
- Parameterized SQL only — never f-string or concatenate user input into SQL.
- No `eval()`, `exec()`, `pickle.loads()`, or `subprocess` with user-controlled strings.
- Generic error messages to clients — no stack traces or internal paths in HTTP responses.
- Auth: implement only when Rules require it. RBAC: 401 unauthenticated, 403 forbidden.
- CORS: explicit origin list; never `allow_origins=["*"]` with credentials.
- Write ONLY under `target-apps/`. Do not modify `db/sql/`. Do not claim Jira/GitLab actions.

## Pre-handoff self-review (mandatory after all writes, before summary)

1. `dev_list_tree(targetApp)` — verify file list is minimal and complete.
2. Route manifest check: every METHOD /path from API surface is handled.
3. Router count check: count(routers/*.py - __init__.py) == count(include_router in main.py).
4. Every subdirectory has `__init__.py`.
5. Every POST has status_code=201 on decorator; every DELETE has status_code=204.
6. Every DB-backed route has Depends(get_db); auth routes use Rules-specified deps (API-key or JWT).
7. List routes match API surface (page object or list[T]) with documented pagination params.
8. conftest.py sets env before app import; no module-level TestClient.
9. No circular imports: schemas → nothing from app/; models → enums only.
10. requirements.txt matches actual imports — no psycopg2-binary, no missing packages.
11. .env.example has every env var config.py reads; .gitignore has .env and .venv/.
12. Postgres apps: every ENUM mapped with SAEnum+with_variant; every uuid with PG_UUID.
13. deploymentHandoff is populated by the CLI in developer-handoff.json — do not paste handoff JSON in your reply.
14. startup_checks.py + lifespan validate_runtime_config; GET /health pings DB; dev exception handler when APP_ENV=development.
15. .env.example every line is KEY=value; README warns about DATABASE_URL= prefix.
16. Bedrock/RDS region vars default to us-east-2 in config.py, .env.example, README env tables, and test conftest setdefaults.
17. Test-vs-implementation contract cross-check (MANDATORY, not optional): for every response value the implementation emits — status field literals (`"ok"`, `"healthy"`, `"running"`), error detail strings, response keys, status codes — open the corresponding test file and confirm the assertion targets the **exact** string the route returns. The route manifest check (item 2) catches missing routes; this check catches value-level drift between code and the tests you just wrote. Common recurring failures:
    - `/health` route returns `{"status": "ok"}` but `test_health.py` asserts `"healthy"` — must match.
    - Route raises `HTTPException(detail="Invalid or missing API key")` but test asserts `"missing api key"` (case/wording) — must match.
    - Route returns a `ContactListPage` object but test asserts `len(data) == 5` instead of `data["total"] == 5` — must match the response shape.
    If you fix the test rather than the code, justify briefly in the handoff summary so reviewers know which contract is canonical.
18. URL path cross-check: for every `@router.get/post/...` decorator, mentally compute `include_router(prefix=) + route_path` and confirm the test calls that exact URL. `/health/health` is a real bug that has shipped before — never double-prefix.
19. Test fixtures must replicate route side-effects: if `POST /findings` creates both a `Finding` AND an initial `status_history` row, then a `sample_finding` fixture that constructs `Finding` via the ORM **must also** insert the matching `status_history` row. Otherwise tests that read the side-effect (`GET /findings/{id}/history`) see an empty list and fail. Rule of thumb: every `db.add(SecondaryModel(...))` call inside a route handler needs a mirror line in the corresponding test fixture, OR the fixture should call the route via the TestClient instead of constructing models directly.
20. ORM models referencing other tables: every `mapped_column(... pg_uuid_column())` that points at another table MUST include `ForeignKey("other_table.id")` as a positional argument. SQL DDL constraints don't propagate to the ORM. Missing FK declaration = `relationship()` raises `NoForeignKeysError` at app startup.
"""

# Backwards-compat alias: legacy "all patterns" prompt. Prefer _build_system_prompt(ctx).
DEVELOPER_SYS_PROMPT = _build_system_prompt(None)


def _resolve_repo_path(relative_path: str, *, write: bool) -> Path:
    raw = relative_path.strip().replace("\\", "/")
    if not raw:
        raise ValueError("path is required")
    candidate = (
        (_REPO_ROOT / raw).resolve()
        if not Path(raw).is_absolute()
        else Path(raw).resolve()
    )
    if not str(candidate).startswith(str(_REPO_ROOT.resolve())):
        raise ValueError(f"path must stay inside repo: {relative_path}")
    if write:
        if not str(candidate).startswith(str(_TARGET_APPS.resolve())):
            raise ValueError("writes only allowed under target-apps/")
        return candidate
    allowed = (
        any(str(candidate).startswith(str(p.resolve())) for p in _READ_PREFIXES)
        or candidate == _REPO_ROOT.resolve()
    )
    if not allowed:
        raise ValueError(f"read not allowed for path: {relative_path}")
    return candidate


def _service_dir(service: str) -> Path:
    return _TARGET_APPS / slugify(service)


def _ensure_service_exists(service: str) -> Path:
    """Ensure target-apps/<service>/ exists. Layout is design-driven — no auto-copy."""
    dest = _service_dir(service)
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _validate_dev_write_path(file_path: Path) -> str | None:
    """Return an error string if this path must not be written by developer-agent."""
    parts = set(file_path.parts)
    if parts & _BLOCKED_PATH_PARTS:
        return "Error: cannot write under .venv/, node_modules/, or cache directories"
    name = file_path.name
    if name == "QA_REPORT.md":
        return "Error: QA_REPORT.md is owned by qa-agent — do not write"
    if file_path.parent.name == "tests" and name.startswith("test_qa_"):
        return "Error: tests/test_qa_*.py is owned by qa-agent — write baseline tests only"
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return (
            "Error: cannot write .env or .env.* secret files — "
            "write .env.example with placeholders; users copy to .env locally"
        )
    return None


def _env_var_names_from_example(written_files: list[str]) -> list[str]:
    """Parse KEY names from a written .env.example."""
    for rel in written_files:
        if not rel.endswith(".env.example"):
            continue
        path = _REPO_ROOT / rel
        if not path.is_file():
            continue
        names: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" in stripped:
                names.append(stripped.split("=", 1)[0].strip())
        return names
    return []


def _deployment_handoff(app: str, written_files: list[str]) -> dict[str, Any]:
    """Structured hints for devops-agent (Docker/ECS/EKS — implemented later)."""
    env_names = _env_var_names_from_example(written_files)
    if "PORT" not in env_names:
        env_names = ["PORT", *env_names]
    return {
        "targetEnvironment": "aws-dev",
        "port": 8000,
        "healthCheckPath": "/health",
        "containerEntrypoint": "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}",
        "envVarNames": env_names,
        "secretsSource": "AWS Secrets Manager, SSM, or ECS task IAM role — not committed .env",
        "dockerReady": True,
        "notes": (
            f"devops-agent owns Dockerfile, CI/CD, and AWS deploy for target-apps/{app}/. "
            "App code must not hardcode localhost or fixed cloud hostnames."
        ),
    }

# Agent Tools

@tool
def dev_list_tree(service: str, subpath: str = "") -> str:
    """List files under target-apps/<service>/ (optionally under subpath)."""
    root = _ensure_service_exists(service)
    base = (root / subpath).resolve()
    if not str(base).startswith(str(root.resolve())):
        return "Error: subpath escapes service directory"
    if not base.exists():
        return f"Error: not found: {base.relative_to(_REPO_ROOT).as_posix()}"
    lines: list[str] = []
    for path in sorted(base.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            lines.append(path.relative_to(_REPO_ROOT).as_posix())
    return "\n".join(lines) if lines else "(no files)"


@tool
def dev_scaffold(service: str, pattern: str, force: bool = False) -> str:
    """Copy golden template infrastructure into target-apps/<service>/.

    Call once per app (Step 2c) before writing domain code. Patterns: B, B+, B++, C.
    Manifest: target-apps/_template/scaffold-manifest.json

    Args:
        service: target app slug (e.g. standup-tracker)
        pattern: B | B+ | B++ | C
        force: when True, overwrite existing scaffold files from _template/
    """
    dest = _ensure_service_exists(service)
    try:
        result = scaffold_service(
            template_dir=_TEMPLATE_DIR,
            service_dir=dest,
            pattern=pattern,
            force=force,
        )
    except (ValueError, FileNotFoundError) as exc:
        return f"SCAFFOLD ERROR: {exc}"

    prefix = f"target-apps/{slugify(service)}/"
    for rel in result["copied"]:
        full = f"{prefix}{rel}"
        if full not in _written_files:
            _written_files.append(full)

    return format_scaffold_report(result, service=slugify(service))


@tool
def dev_read_file(path: str) -> str:
    """Read a repo file. Allowed: target-apps/, docs/, agents/, inputs/.
    Use to read PRD, design doc, database handoff, and scraped markdown."""
    try:
        file_path = _resolve_repo_path(path, write=False)
    except ValueError as exc:
        return f"Error: {exc}"
    if not file_path.is_file():
        return f"Error: not a file: {path}"
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Error: binary or non-utf8 file: {path}"


@tool
def dev_write_file(path: str, content: str) -> str:
    """Write a single file under target-apps/. Prefer `dev_write_files` for ≥3 related files.

    Blocked: .env (use .env.example), QA_REPORT.md, tests/test_qa_*.py,
    .venv/, node_modules/, cache dirs.
    Example: target-apps/my-svc/app/routers/items.py
    """
    try:
        file_path = _resolve_repo_path(path, write=True)
    except ValueError as exc:
        return f"Error: {exc}"
    blocked = _validate_dev_write_path(file_path)
    if blocked:
        return blocked
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8", newline="\n")
    rel = file_path.relative_to(_REPO_ROOT).as_posix()
    if rel not in _written_files:
        _written_files.append(rel)
    return f"Wrote {rel} ({len(content)} bytes)"


@tool
def dev_write_files(files: dict[str, str]) -> str:
    """Write multiple files in ONE tool call. Pass a mapping of `{path: content}`.

    Use this for batched scaffolding (all models, all routers, all schemas in one call)
    instead of many `dev_write_file` calls — drastically reduces tool call count and
    LLM round-trips. Each path follows the same scoping/blocking rules as `dev_write_file`.

    Returns a summary: how many files were written + which ones failed validation.
    Continues on per-file errors (doesn't abort the whole batch); errored entries are
    reported in the return value but successfully-written files are still on disk.

    Example:
        dev_write_files({
            "target-apps/my-svc/app/models/item.py": "from sqlalchemy ...",
            "target-apps/my-svc/app/models/order.py": "from sqlalchemy ...",
            "target-apps/my-svc/app/routers/items.py": "from fastapi ...",
        })
    """
    if not isinstance(files, dict) or not files:
        return "Error: files must be a non-empty dict of {path: content}"

    written: list[str] = []
    errors: list[str] = []
    for path, content in files.items():
        if not isinstance(path, str) or not isinstance(content, str):
            errors.append(f"{path!r}: path and content must both be strings")
            continue
        try:
            file_path = _resolve_repo_path(path, write=True)
        except ValueError as exc:
            errors.append(f"{path}: {exc}")
            continue
        blocked = _validate_dev_write_path(file_path)
        if blocked:
            errors.append(f"{path}: {blocked}")
            continue
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8", newline="\n")
        rel = file_path.relative_to(_REPO_ROOT).as_posix()
        if rel not in _written_files:
            _written_files.append(rel)
        written.append(rel)

    summary = f"Wrote {len(written)} file(s)"
    if errors:
        summary += f"; {len(errors)} error(s):\n  - " + "\n  - ".join(errors)
    return summary


def _parse_dotenv_file(path: Path) -> dict[str, str]:
    """Parse KEY=value lines from .env.example (ignores comments and malformed lines)."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, val = stripped.split("=", 1)
        values[key.strip()] = val.strip()
    return values


def _validate_env_example(service_dir: Path) -> list[str]:
    """Return error lines for malformed .env.example (common cause of silent SQLite fallback)."""
    env_example = service_dir / ".env.example"
    if not env_example.is_file():
        return ["ENV_EXAMPLE FAILED: .env.example not found"]

    errors: list[str] = []
    text = env_example.read_text(encoding="utf-8")
    lines = text.splitlines()

    has_database_url_key = False
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            errors.append(
                f"  line {idx}: missing '=' — use KEY=value (e.g. DATABASE_URL=postgresql+psycopg://...)"
            )
            continue
        key, _ = stripped.split("=", 1)
        if key.strip() == "DATABASE_URL":
            has_database_url_key = True

    if not has_database_url_key:
        # Postgres apps almost always need this; bare URL lines are the #1 user mistake.
        postgres_hint = any(
            "postgresql" in ln.lower() or "psycopg" in ln.lower()
            for ln in lines
            if ln.strip() and not ln.strip().startswith("#")
        )
        if postgres_hint:
            errors.append(
                "  found a Postgres URL without DATABASE_URL= prefix — users will paste this wrong"
            )
        else:
            errors.append("  DATABASE_URL= line missing from .env.example")

    if errors:
        return ["ENV_EXAMPLE FAILED:"] + errors
    return ["ENV_EXAMPLE OK"]


def _python_for_service(service_dir: Path) -> str:
    import platform

    if platform.system() == "Windows":
        venv_python = service_dir / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = service_dir / ".venv" / "bin" / "python"
    return str(venv_python) if venv_python.is_file() else "python"


def _validation_env(service_dir: Path) -> dict[str, str]:
    """Test env: SQLite for smoke tests; schema/keys from .env.example when present."""
    env = {**os.environ}
    example_vars = _parse_dotenv_file(service_dir / ".env.example")
    env.update(example_vars)
    env["APP_ENV"] = "test"
    env["SKIP_STARTUP_CHECKS"] = "1"
    env["DATABASE_URL"] = "sqlite:///:memory:"
    if not env.get("API_KEY"):
        env["API_KEY"] = "test-key"
    env.setdefault("JWT_SECRET", example_vars.get("JWT_SECRET") or "test-secret-not-for-prod")
    env.setdefault("JWT_SECRET_KEY", env["JWT_SECRET"])
    env.setdefault("JWT_EXPIRE_MINUTES", "60")
    env.setdefault("JWT_TTL_HOURS", "8")
    # Valid Fernet key for encryption smoke tests (32 zero bytes, url-safe base64)
    env.setdefault(
        "ASSET_ENCRYPTION_KEY",
        example_vars.get("ASSET_ENCRYPTION_KEY")
        or "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    )
    env.setdefault("AWS_REGION", "us-east-2")
    return env


_ROUTER_ANTIPATTERN_RES = (
    re.compile(r"\bCurrentUser\s*=\s*Depends\s*\("),
    re.compile(r"\bDbSession\s*=\s*Depends\s*\("),
    re.compile(r"Annotated\s*\[[^\]]+Depends[^\]]*\]\s*=\s*Depends\s*\("),
)


def _scan_router_antipatterns(service_dir: Path) -> list[str]:
    """Static scan for FastAPI dependency mistakes that crash at import."""
    errors: list[str] = []
    routers = service_dir / "app" / "routers"
    if not routers.is_dir():
        return errors
    for path in routers.glob("*.py"):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(service_dir).as_posix()
        for pattern in _ROUTER_ANTIPATTERN_RES:
            if pattern.search(text):
                errors.append(
                    f"{rel}: double Depends() on Annotated auth type — use "
                    "`current_user: CurrentUser` only (no `= Depends()`); "
                    "put CurrentUser before Query params with defaults"
                )
                break
    return errors


def run_service_validation(
    service: str,
    *,
    run_pytest: bool = True,
) -> tuple[bool, str]:
    """Host-side validation gate. Returns (passed, full report)."""
    import subprocess

    service_dir = _service_dir(service)
    if not service_dir.is_dir():
        return False, f"Error: target-apps/{service}/ does not exist"

    reqs = service_dir / "requirements.txt"
    if not reqs.is_file():
        return False, f"Error: target-apps/{service}/requirements.txt not found"

    python_cmd = _python_for_service(service_dir)
    env = _validation_env(service_dir)
    output_parts: list[str] = []

    required_files = [
        "app/__init__.py",
        "app/main.py",
        "app/config.py",
        "app/database.py",
        "app/startup_checks.py",
        "app/routers/__init__.py",
        "app/routers/health.py",
    ]
    missing = [f for f in required_files if not (service_dir / f).is_file()]
    if missing:
        output_parts.append("STRUCTURE FAILED — missing golden template files:")
        for f in missing:
            output_parts.append(f"  - {f}")
        return False, "\n".join(output_parts)
    output_parts.append("STRUCTURE OK")

    env_results = _validate_env_example(service_dir)
    output_parts.extend(env_results)
    if env_results[0].startswith("ENV_EXAMPLE FAILED"):
        return False, "\n".join(output_parts)

    antipattern_errors = _scan_router_antipatterns(service_dir)
    if antipattern_errors:
        output_parts.append("ROUTER_ANTIPATTERN FAILED (fix before import will work):")
        output_parts.extend(f"  - {e}" for e in antipattern_errors)
        return False, "\n".join(output_parts)
    output_parts.append("ROUTER_ANTIPATTERN OK")

    seed_sql = (
        list((service_dir / "db" / "sql").glob("*seed*.sql"))
        if (service_dir / "db" / "sql").is_dir()
        else []
    )
    if seed_sql:
        verify_script = _REPO_ROOT / "agents" / "_shared" / "verify_seed_bcrypt.py"
        if verify_script.is_file():
            try:
                result = subprocess.run(
                    [
                        python_cmd,
                        str(verify_script),
                        "--target-app",
                        service,
                        "--repo-root",
                        str(_REPO_ROOT),
                    ],
                    cwd=str(service_dir),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    detail = (result.stdout + result.stderr).strip()
                    if "without documented password" in detail:
                        # Missing password comment = real error; materialize can't run without it
                        output_parts.append(
                            f"SEED_BCRYPT FAILED — __BCRYPT_PLACEHOLDER__ without documented "
                            f"password in SQL comment (add `-- Password for all seed users: \"…\"`):\n{detail}"
                        )
                        return False, "\n".join(output_parts)
                    output_parts.append(
                        f"SEED_BCRYPT WARN (non-blocking — hash mismatch or antipattern; "
                        f"check whether apply_sql_to_rds.py ran):\n{detail}"
                    )
                else:
                    output_parts.append("SEED_BCRYPT OK")
                    # Remind developer agent when placeholders still need pipeline to materialize
                    has_placeholders = any(
                        "__BCRYPT_PLACEHOLDER__" in p.read_text(encoding="utf-8", errors="replace")
                        for p in seed_sql
                        if "fix" not in p.name.lower()
                    )
                    if has_placeholders:
                        output_parts.append(
                            f"SEED_BCRYPT NOTE — seed SQL uses __BCRYPT_PLACEHOLDER__ "
                            f"(RDS login will 401 until materialized):\n"
                            f"  Auto (full pipeline): python scripts/apply_sql_to_rds.py --target-app {service}\n"
                            f"  Manual (after SQL already applied): "
                            f"python agents/_shared/materialize_seed_passwords.py --target-app {service}\n"
                            f"  README Seed Users section MUST include this command."
                        )
            except subprocess.TimeoutExpired:
                output_parts.append("SEED_BCRYPT TIMEOUT (non-blocking)")

    from _shared.validate_rds_parity import validate_rds_parity, validate_rds_parity_warnings

    rds_errors = validate_rds_parity(service_dir)
    if rds_errors:
        output_parts.append("RDS_PARITY FAILED (blocks RDS smoke / Streamlit — pytest may still pass):")
        output_parts.extend(f"  - {e}" for e in rds_errors)
        return False, "\n".join(output_parts)
    output_parts.append("RDS_PARITY OK")
    for warn in validate_rds_parity_warnings(service_dir):
        output_parts.append(f"RDS_PARITY WARN: {warn}")

    from _shared.validate_ui_parity import validate_ui_parity, validate_ui_parity_blocking

    ui_errors = validate_ui_parity_blocking(service_dir, _REPO_ROOT)
    if ui_errors:
        output_parts.append("UI_PARITY FAILED (API vs design / Streamlit coverage):")
        output_parts.extend(f"  - {e}" for e in ui_errors)
        return False, "\n".join(output_parts)
    output_parts.append("UI_PARITY OK")
    for msg in validate_ui_parity(service_dir, _REPO_ROOT):
        if " WARN:" in msg:
            output_parts.append(f"UI_PARITY WARN: {msg}")

    if (service_dir / "app" / "startup_checks.py").is_file():
        startup_env = {**os.environ, **_parse_dotenv_file(service_dir / ".env.example")}
        startup_env["APP_ENV"] = "development"
        startup_env.pop("SKIP_STARTUP_CHECKS", None)
        try:
            result = subprocess.run(
                [python_cmd, "-c", _STARTUP_CONFIG_SCRIPT],
                cwd=str(service_dir),
                capture_output=True,
                text=True,
                timeout=15,
                env=startup_env,
            )
            if result.returncode != 0:
                blocking = True
                output_parts.append(
                    "STARTUP_CONFIG FAILED (uvicorn would refuse to start):\n{}{}".format(
                        result.stdout, result.stderr
                    )
                )
                return False, "\n".join(output_parts)
            output_parts.append("STARTUP_CONFIG OK")
        except subprocess.TimeoutExpired:
            return False, "\n".join(output_parts + ["STARTUP_CONFIG TIMEOUT"])

    import_cmd = [python_cmd, "-c", "from app.main import app; print('IMPORT_OK')"]
    try:
        result = subprocess.run(
            import_cmd,
            cwd=str(service_dir),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if result.returncode != 0:
            output_parts.append("IMPORT FAILED (exit code {}):\n{}{}".format(
                result.returncode,
                result.stdout,
                result.stderr,
            ))
            if "Cannot specify `Depends` in `Annotated`" in result.stderr:
                output_parts.append(
                    "Hint: remove `= Depends()` from CurrentUser/DbSession parameters"
                )
            if "parameter without a default follows parameter with a default" in result.stderr:
                output_parts.append(
                    "Hint: move CurrentUser/DbSession before Query(...) parameters"
                )
            return False, "\n".join(output_parts)
        output_parts.append("IMPORT OK")
    except subprocess.TimeoutExpired:
        return False, "\n".join(output_parts + ["IMPORT TIMEOUT (>30s)"])

    health_cmd = [python_cmd, "-c", _HEALTH_SMOKE_SCRIPT]
    try:
        result = subprocess.run(
            health_cmd,
            cwd=str(service_dir),
            capture_output=True,
            text=True,
            timeout=45,
            env=env,
        )
        if result.returncode != 0:
            output_parts.append("HEALTH FAILED:\n{}{}".format(result.stdout, result.stderr))
            return False, "\n".join(output_parts)
        output_parts.append(result.stdout.strip() or "HEALTH OK")
    except subprocess.TimeoutExpired:
        return False, "\n".join(output_parts + ["HEALTH TIMEOUT (>45s)"])

    tests_dir = service_dir / "tests"
    if run_pytest and tests_dir.is_dir():
        pytest_cmd = [python_cmd, "-m", "pytest", "tests/", "-q", "--tb=short"]
        try:
            result = subprocess.run(
                pytest_cmd,
                cwd=str(service_dir),
                capture_output=True,
                text=True,
                timeout=180,
                env=env,
            )
            stdout = result.stdout[-4000:] if len(result.stdout) > 4000 else result.stdout
            stderr = result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr
            if result.returncode == 0:
                output_parts.append(f"PYTEST OK:\n{stdout}")
            else:
                output_parts.append(f"PYTEST FAILED (exit {result.returncode}):\n{stdout}\n{stderr}")
                if "SQLite Date type only accepts Python date objects" in stdout + stderr:
                    output_parts.append(
                        "Hint: use date(2024, 1, 1) in ORM fixtures, not '2024-01-01' strings"
                    )
                return False, "\n".join(output_parts)
        except subprocess.TimeoutExpired:
            return False, "\n".join(output_parts + ["PYTEST TIMEOUT (>180s)"])
    elif run_pytest:
        output_parts.append("PYTEST SKIPPED: no tests/ directory")

    return True, "\n".join(output_parts)


_STARTUP_CONFIG_SCRIPT = """
from app.config import get_settings
from app.startup_checks import validate_runtime_config
validate_runtime_config(get_settings())
print("STARTUP_CONFIG OK")
"""


_HEALTH_SMOKE_SCRIPT = """
import os, json
from fastapi.testclient import TestClient
from app.main import app

try:
    from app.database import Base, engine
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"DB_SETUP_WARNING: {e} (tables may not be created)")

with TestClient(app) as client:
    # 1. Health check
    for path in ("/health", "/healthz"):
        resp = client.get(path)
        if resp.status_code in (200, 503):
            print(f"HEALTH_OK path={path} status={resp.status_code} body={resp.json()}")
            break
    else:
        raise SystemExit("No working health endpoint at /health or /healthz")

    # 2. Auto-discover GET routes from OpenAPI and smoke-test them
    api_key = os.environ.get("API_KEY", "test-key")
    headers = {"X-API-Key": api_key}
    tested = 0
    openapi = client.get("/openapi.json")
    if openapi.status_code == 200:
        spec = openapi.json()
        for route_path, methods in spec.get("paths", {}).items():
            if route_path in ("/health", "/healthz", "/", "/openapi.json", "/docs", "/redoc"):
                continue
            if "get" not in methods:
                continue
            if "{" in route_path:
                continue
            resp = client.get(route_path, headers=headers)
            status = resp.status_code
            ok = status in (200, 401, 403, 404, 422)
            tag = "API_ROUTE_OK" if ok else "API_ROUTE_WARN"
            print(f"{tag} GET {route_path} status={status}")
            tested += 1
            if tested >= 3:
                break
    if tested == 0:
        print("API_ROUTE_SKIPPED: no GET list routes found in OpenAPI spec (optional)")
"""


@tool
def dev_validate_app(service: str, run_pytest: bool = True) -> str:
    """Validate the generated app can start and pass tests.

    Runs structure, env-example, router antipattern scan, seed bcrypt (warn-only),
    startup config, import, health smoke, and pytest (default on).

    Returns the full report. If output contains FAILED, fix files and call again.
    Do NOT declare success to the user until you see IMPORT OK and PYTEST OK.
    """
    passed, report = run_service_validation(service, run_pytest=run_pytest)
    if passed:
        return report + "\n\nVALIDATION PASSED — safe to hand off."
    return report + "\n\nVALIDATION FAILED — fix all errors above and call dev_validate_app again."


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _strip_duplicate_handoff_sections(text: str) -> str:
    """Remove file lists and handoff JSON if the model still emitted them."""
    patterns = (
        r"\n## Files written\r?\n.*",
        r"\n## Context handoff\r?\n```json\r?\n.*?\r?\n```\s*",
        r"\n### 2\. Files Written\r?\n```.*?```\s*",
        r"\n### 6\. Handoff JSON\r?\n\s*```json\r?\n.*?\r?\n```\s*",
        r"\n```json\r?\n\s*\{\s*\"writtenFiles\".*?\r?\n```\s*",
    )
    out = text
    for pattern in patterns:
        out = re.sub(pattern, "", out, flags=re.DOTALL)
    return out.strip()


def _write_developer_handoff(app: str, handoff: dict[str, Any]) -> str:
    """Persist handoff JSON for qa-agent / devops-agent; return repo-relative path."""
    PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
    path = PIPELINE_DIR / f"{slugify(app)}.developer-handoff.json"
    path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    return path.relative_to(_REPO_ROOT).as_posix()


def _max_output_tokens() -> int:
    return int(os.getenv("DEVELOPER_AGENT_MAX_TOKENS", "32768"))


def _thinking_enabled() -> bool:
    return os.getenv("DEVELOPER_AGENT_THINKING", "").strip().lower() in ("1", "true", "yes")


def _thinking_budget_tokens() -> int:
    return int(os.getenv("DEVELOPER_AGENT_THINKING_BUDGET", "8192"))


class _DeveloperCallbackHandler:
    """Stream tool calls, optional thinking, and feed telemetry."""

    def __init__(self, *, show_thinking: bool, telemetry: RunTelemetry | None = None) -> None:
        self._show_thinking = show_thinking
        self.telemetry = telemetry

    def __call__(self, **kwargs: Any) -> None:
        reasoning_text = kwargs.get("reasoningText")
        if self._show_thinking and reasoning_text:
            print(reasoning_text, end="", file=sys.stderr)

        event = kwargs.get("event", {})
        tool_use = event.get("contentBlockStart", {}).get("start", {}).get("toolUse")
        if tool_use:
            name = tool_use.get("name", "<unknown>")
            if self.telemetry is not None:
                self.telemetry.record_tool(name)
                print(
                    f"\n[developer-agent] Tool #{self.telemetry.tool_count}: {name}",
                    file=sys.stderr,
                )
            else:
                print(f"\n[developer-agent] Tool: {name}", file=sys.stderr)

        # Capture Bedrock usage tokens from streamed metadata events.
        if self.telemetry is not None:
            usage = usage_from_event(kwargs) or usage_from_event(event)
            if usage:
                self.telemetry.record_usage(usage)


def _coding_model_id() -> str:
    return os.getenv(
        "CODING_MODEL_ID",
        os.getenv("MODEL_ID", "us.anthropic.claude-opus-4-6-v1"),
    )


def _coding_model() -> BedrockModel:
    read_timeout = int(os.getenv("BEDROCK_READ_TIMEOUT", "600"))
    model_kwargs: dict[str, Any] = {
        "model_id": _coding_model_id(),
        "region_name": os.getenv("AWS_REGION", "us-east-2"),
        "max_tokens": _max_output_tokens(),
        "streaming": True,
        "cache_config": CacheConfig(strategy="auto"),
        "cache_tools": "default",
        "boto_client_config": botocore.config.Config(
            read_timeout=read_timeout,
            connect_timeout=10,
            retries={"mode": "standard", "max_attempts": 2},
        ),
    }
    if _thinking_enabled():
        # "adaptive" thinking is only supported on Claude 4.5+; Sonnet 4 requires "enabled"|"disabled".
        model_kwargs["additional_request_fields"] = {
            "thinking": {"type": "enabled", "budget_tokens": _thinking_budget_tokens()},
        }

    # ── Sonnet 4.6 upgrade — uncomment this block (and delete the one above) when MODEL_ID/CODING_MODEL_ID
    # in .env are switched to a Sonnet 4.5+ inference profile. It makes the thinking type env-driven so you
    # can flip between "enabled"/"adaptive"/"disabled" via THINKING_TYPE without touching code again.
    #
    # if _thinking_enabled():
    #     thinking_type = os.getenv("THINKING_TYPE", "adaptive")  # "enabled" | "adaptive" | "disabled"
    #     model_kwargs["additional_request_fields"] = {
    #         "thinking": {"type": thinking_type, "budget_tokens": _thinking_budget_tokens()},
    #     }
    return BedrockModel(**model_kwargs)


def _build_agent(
    ctx: dict[str, Any] | None = None,
    *,
    telemetry: RunTelemetry | None = None,
) -> Agent:
    return Agent(
        agent_id=AGENT_NAME,
        name=AGENT_NAME,
        description=(
            "Implements backend API code under target-apps/ from PRD, design doc, "
            "database-agent handoff, and scraped research. "
            "Patterns: in-memory, postgres, postgres-llm, rag, streamlit "
            "(legacy aliases: A, B, B+, B++, C)."
        ),
        model=_coding_model(),
        system_prompt=_build_system_prompt(ctx),
        tools=[dev_list_tree, dev_scaffold, dev_read_file, dev_write_file, dev_write_files, dev_validate_app],
        callback_handler=_DeveloperCallbackHandler(
            show_thinking=_thinking_enabled(),
            telemetry=telemetry,
        ),
    )


def _user_message(task: str, context: dict[str, Any] | None) -> str:
    if not context:
        return task
    return f"{task}\n\nContext:\n{json.dumps(context, indent=2)}"


def _resolve_target_app(name: str | None, context: dict[str, Any] | None) -> str:
    return resolve_target_app(name, context, env_var="DEVELOPER_TARGET_APP")


def _enrich_developer_context(ctx: dict[str, Any]) -> None:
    """Add developer-specific paths that enrich_handoff_context doesn't cover."""
    app = slugify(str(ctx["targetApp"]))
    service_dir = _REPO_ROOT / "target-apps" / app

    # Database-agent handoff file
    if not ctx.get("databaseHandoffPath"):
        for candidate in (
            service_dir / "db" / "HANDOFF.md",
            service_dir / "db" / "handoff.md",
            service_dir / "db" / "database_handoff.md",
            _REPO_ROOT / "agents" / "pipeline" / f"{app}.db-handoff.md",
        ):
            if candidate.is_file():
                ctx["databaseHandoffPath"] = candidate.relative_to(_REPO_ROOT).as_posix()
                break

    # Scraped content from web-crawler-agent
    if not ctx.get("scrapedMarkdownPaths"):
        scraped_dir = _REPO_ROOT / "docs" / "PRD" / "scraped" / app
        if scraped_dir.is_dir():
            paths = [
                p.relative_to(_REPO_ROOT).as_posix()
                for p in sorted(scraped_dir.rglob("*.md"))
                if p.is_file()
            ]
            if paths:
                ctx["scrapedMarkdownPaths"] = paths

    if not ctx.get("dbBackend"):
        has_sql = bool(ctx.get("preferredSqlPath") or ctx.get("dbOutputDir"))
        has_nosql = bool(
            (service_dir / "db" / "nosql").is_dir()
            or ctx.get("preferredNoSqlPath")
        )
        if has_sql and has_nosql:
            ctx["dbBackend"] = "postgres+mongodb"
        elif has_nosql:
            ctx["dbBackend"] = "mongodb"
        elif has_sql:
            ctx["dbBackend"] = "postgres"

    if not ctx.get("templateDir") and _TEMPLATE_DIR.is_dir() and any(_TEMPLATE_DIR.iterdir()):
        ctx["templateDir"] = _TEMPLATE_DIR.relative_to(_REPO_ROOT).as_posix()


def _build_context(
    *,
    target_app: str,
    jira_key: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    service_path = _ensure_service_exists(target_app)
    ctx: dict[str, Any] = {
        "targetApp": target_app,
        "targetAppDir": service_path.relative_to(_REPO_ROOT).as_posix(),
    }
    if jira_key:
        ctx["jiraKey"] = jira_key
    if extra:
        ctx.update(extra)
    return ctx


def run_task(
    task: str,
    context: dict[str, Any] | None = None,
    *,
    target_app: str | None = None,
    jira_key: str | None = None,
) -> tuple[str, list[str], str | None]:
    global _written_files
    _written_files = []

    app = _resolve_target_app(target_app, context)
    ctx = context if context is not None else _build_context(target_app=app, jira_key=jira_key)
    ctx.setdefault("targetApp", app)
    ctx.setdefault("targetAppDir", _ensure_service_exists(app).relative_to(_REPO_ROOT).as_posix())

    enrich_handoff_context(ctx, include_db_paths=True)
    _enrich_developer_context(ctx)

    if jira_key:
        ctx.setdefault("jiraKey", jira_key)

    telemetry = RunTelemetry(AGENT_NAME, target_app=app)
    agent = _build_agent(ctx, telemetry=telemetry)
    summary = _strip_duplicate_handoff_sections(str(agent(_user_message(task, ctx))))

    written = _dedupe_preserve_order(_written_files)
    handoff_rel: str | None = None
    if written:
        has_env_example = any(p.endswith(".env.example") for p in written)
        handoff: dict[str, Any] = {
            "writtenFiles": written,
            "targetApp": app,
            "jiraKey": ctx.get("jiraKey"),
            "dbBackend": ctx.get("dbBackend"),
            "designDocPath": ctx.get("designDocPath"),
            "prdPath": ctx.get("prdPath"),
            "databaseHandoffPath": ctx.get("databaseHandoffPath"),
            "runCommandLocal": f"cd target-apps/{app} && uvicorn app.main:app --reload --port 8000",
            "testCommand": f"cd target-apps/{app} && pytest tests/ -q",
            "deploymentHandoff": _deployment_handoff(app, written),
        }
        handoff["runCommand"] = handoff["runCommandLocal"]
        if has_env_example:
            handoff["userSetupCommand"] = (
                f"cd target-apps/{app} && cp .env.example .env  "
                "# Windows: copy .env.example .env — then edit real values locally"
            )
            handoff["envVarsRequired"] = _env_var_names_from_example(written)
        handoff_rel = _write_developer_handoff(app, handoff)

    # Telemetry: tokens, cache hits, wall-clock, file count; persist for next-run delta.
    telemetry.extra = {
        "filesWritten": len(written),
        "pattern": _select_pattern_keys(ctx) or "all",
    }
    telemetry.print_summary()
    telemetry.persist()

    return summary, written, handoff_rel


def serve_a2a(host: str = "127.0.0.1", port: int = A2A_PORT) -> None:
    skills = [
        AgentSkill(
            id="implement_feature",
            name="implement_feature",
            description=(
                "Implement backend API + optional Streamlit UI under target-apps/. "
                "Patterns A/B/B+/B++/C. Stack driven by design doc tech stack section."
            ),
            tags=["development", "fastapi", "python", "streamlit", "rag", "bedrock"],
        )
    ]
    agent = _build_agent()
    A2AServer(agent, host=host, port=port, skills=skills).serve()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Developer agent — Strands + Bedrock + file tools"
    )
    parser.add_argument(
        "--task",
        help="Optional task override. Default: full pipeline task.",
    )
    parser.add_argument(
        "--target-app",
        help="Service folder under target-apps/ (from --target-app, context targetApp, or PIPELINE_TARGET_APP)",
    )
    parser.add_argument(
        "--no-auto-context",
        action="store_true",
        help="Do not load agents/pipeline/<target-app>.context.json automatically.",
    )
    parser.add_argument("--jira-key", help="Jira key (e.g. SAAP-3)")
    load_context_extra(parser)
    parser.add_argument(
        "--serve-a2a", action="store_true", help=f"Start A2A server on :{A2A_PORT}"
    )
    parser.add_argument("--port", type=int, default=A2A_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if args.serve_a2a:
        serve_a2a(host=args.host, port=args.port)
        return

    if not args.task:
        args.task = DEFAULT_PIPELINE_TASK

    try:
        extra, target = resolve_cli_context(
            args.target_app,
            parse_context_args(args),
            no_auto_context=args.no_auto_context,
            env_var="DEVELOPER_TARGET_APP",
    )
    except TargetAppRequiredError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    if extra.get("_contextFile"):
        print(f"[developer-agent] Context (auto): {extra['_contextFile']}", file=sys.stderr)

    enrich_handoff_context(extra, include_db_paths=True)
    _enrich_developer_context(extra)

    ctx = _build_context(target_app=target, jira_key=args.jira_key, extra=extra or None)

    auto_pattern = os.getenv("DEVELOPER_AGENT_AUTO_PATTERN", "").strip().lower() in {"1", "true", "yes"}
    print("", file=sys.stderr)
    print("=" * 64, file=sys.stderr)
    print(
        f"  AGENT: {AGENT_NAME}  |  prompt-cache: auto  |  cache_tools: default"
        f"  |  auto-pattern: {'on' if auto_pattern else 'off'}",
        file=sys.stderr,
    )
    print("=" * 64, file=sys.stderr)
    print(f"[developer-agent] Model      : {_coding_model_id()}", file=sys.stderr)
    if _thinking_enabled():
        print(
            f"[developer-agent] Thinking   : on (budget {_thinking_budget_tokens()} tokens)",
            file=sys.stderr,
        )
    print(f"[developer-agent] Target app : {ctx['targetAppDir']}", file=sys.stderr)
    print(f"[developer-agent] Design doc : {resolve_design_doc_path(ctx)}", file=sys.stderr)
    if ctx.get("prdPath") or ctx.get("prd_path"):
        print(f"[developer-agent] PRD        : {ctx.get('prdPath') or ctx.get('prd_path')}", file=sys.stderr)
    if ctx.get("databaseHandoffPath"):
        print(
            f"[developer-agent] DB handoff : {ctx['databaseHandoffPath']}",
            file=sys.stderr,
        )
    elif ctx.get("preferredSqlPath") or ctx.get("dbOutputDir"):
        print(
            "[developer-agent] DB handoff : (not found — run database-agent first; "
            "expected target-apps/<app>/db/HANDOFF.md)",
            file=sys.stderr,
        )
    if ctx.get("preferredSqlPath"):
        print(f"[developer-agent] SQL dir    : {ctx['preferredSqlPath']}", file=sys.stderr)
    if ctx.get("scrapedMarkdownPaths"):
        print(
            f"[developer-agent] Scraped docs : {len(ctx['scrapedMarkdownPaths'])} file(s)",
            file=sys.stderr,
        )
    print("[developer-agent] Running...", file=sys.stderr)

    max_validate_retries = int(os.getenv("DEVELOPER_AGENT_VALIDATE_RETRIES", "2"))
    task = args.task
    result = ""
    written: list[str] = []
    handoff_rel: str | None = None

    for attempt in range(max_validate_retries + 1):
        if attempt > 0:
            print(
                f"[developer-agent] Validation retry {attempt}/{max_validate_retries}...",
                file=sys.stderr,
            )
        result, written, handoff_rel = run_task(
            task,
            ctx,
            target_app=target,
            jira_key=args.jira_key,
        )
        passed, validate_report = run_service_validation(target, run_pytest=True)
        print("\n=== Host validation gate ===", file=sys.stderr)
        print(validate_report, file=sys.stderr)
        if passed:
            print("[developer-agent] Host validation PASSED", file=sys.stderr)
            break
        if attempt >= max_validate_retries:
            print(
                "[developer-agent] Host validation FAILED after "
                f"{max_validate_retries + 1} attempt(s) — exiting non-zero.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        task = (
            "Host validation failed after your implementation. Fix ALL blocking errors "
            "before handoff. Call dev_validate_app(run_pytest=True) until you see "
            "IMPORT OK and PYTEST OK.\n\n"
            f"{validate_report}\n\n"
            "Do NOT declare the app complete until validation passes."
        )
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(result)
    if written:
        print(
            f"[developer-agent] Wrote {len(written)} file(s) under {ctx['targetAppDir']}/",
            file=sys.stderr,
        )
    else:
        service_dir = _service_dir(str(ctx.get("targetApp", target)))
        has_files = service_dir.is_dir() and any(service_dir.rglob("*.py"))
        msg = (
            "No new files written (existing code detected — agent may have reviewed only)."
            if has_files
            else "WARNING: no files written under target-apps/."
        )
        print(f"[developer-agent] {msg}", file=sys.stderr)
    if handoff_rel:
        print(f"[developer-agent] Handoff   : {handoff_rel}", file=sys.stderr)


if __name__ == "__main__":
    main()