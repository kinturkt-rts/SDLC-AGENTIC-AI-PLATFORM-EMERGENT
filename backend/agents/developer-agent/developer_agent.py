"""Developer agent — Strands + Bedrock; generates target-apps code and developer handoff."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TARGET_APPS = _REPO_ROOT / "target-apps"
_DEV_AGENT_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)

sys.path.insert(0, str(_REPO_ROOT / "agents"))
sys.path.insert(0, str(_DEV_AGENT_DIR))
from scaffold import format_scaffold_report, scaffold_service
from _shared.artifact_store import (
    is_s3_store,
    list_run_artifact_keys,
    put_artifact,
    put_context,
    read_repo_artifact,
    resolve_run_id,
    write_repo_artifact,
)
from _shared import template_store
from _shared.context_cli import load_context_extra, parse_context_args
from _shared.env import load_repo_env
from _shared.derive_enums import derive_enums_for_app
from _shared.runner import coding_model_id
from _shared.pipeline_context import (
    PIPELINE_DIR,
    TargetAppRequiredError,
    _is_cloud_store,
    developer_handoff_rel_for_app,
    merge_run_handoff_context,
    openapi_rel_for_app,
    resolve_cli_context,
    resolve_design_doc_path,
    resolve_target_app,
    slugify,
    target_app_root_rel,
)
from _shared.telemetry import RunTelemetry, usage_from_event
from _shared.pg_test_schema import setup_temp_pg_test_schema, teardown_temp_pg_schema

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


def _resolve_template_dir() -> Path:
    """Local repo copy wins for local dev; else fetch from S3 (cloud runtime)."""
    try:
        return template_store.get_template_dir()
    except Exception:
        return _TARGET_APPS / "_template"

_TEMPLATE_DIR = _resolve_template_dir()


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
Extract EVERY METHOD + path from the design **API surface** heading — for EVERY entity the design
describes, not just the first one or two — and write a numbered manifest:
  # Route manifest:
  # 1. POST   /items          status=201
  # 2. GET    /items          status=200  list[ItemOut]
  # 3. GET    /items/{id}     status=200  ItemOut | 404
  # 4. DELETE /items/{id}     status=204
  # 5. GET    /health         status=200
Do NOT write a single file until every route has a planned: handler + router file + request
schema + response schema. After writing all files, verify manifest is fully covered.
Missing any route = the agent must catch it here, not during re-run.

**Do not silently narrow an entity's operations.** If the design gives an entity full CRUD
(GET-list, GET-by-id, POST, PATCH/PUT, DELETE), the manifest must include all of those operations
for that entity — implementing only list+create for one entity while giving another entity full
CRUD, with no stated reason, is a scope gap, not an acceptable simplification.

**Safety valve (the only acceptable way to reduce scope):** if a specific route genuinely cannot be
implemented (e.g. it depends on an external system this run has no credentials/access for), do NOT
drop it from the manifest silently. Mark it `# NOT IMPLEMENTED: <method> <path> — <specific reason>`
in the manifest AND repeat that exact line in the `### not_implemented` section of your final handoff
summary (Step 5b). A route that is simply absent, with no NOT IMPLEMENTED line anywhere, is a bug.

**Step 0b — UI manifest (Pattern C / requiresStreamlit ONLY — skip for API-only apps)**
When `deliveryProfile.requiresStreamlit` is true, build a second manifest from design §4 + PRD roles:
  # UI manifest (Streamlit calls API over HTTP — never import app/):
  # - Auth gate: login_form() shown when st.session_state.token absent → ALL other content hidden
  # - GET  /api/v1/work-orders     → requester "My Orders" table + admin triage table
  # - GET  /api/v1/sites           → admin Sites table + requester create-WO selectbox
  # - GET  /api/v1/dashboard/sla   → leadership dashboard
  # - Role tabs: viewer=[A,B]; editor=[A,B,C]; admin=[A,B,C,D]
The auth gate line is REQUIRED when the PRD or design Rules specify any auth/RBAC requirement.
"Unauthenticated users see only the login screen" is a UI requirement, NOT just an API 401 — API guards
alone do NOT satisfy it; the Streamlit app itself must enforce it.
Every **collection GET** in design §4 (paths without `{id}`) MUST have a Streamlit `_get()` in at least one role view.
Every **POST create** on a collection (`POST /api/v1/sites`) MUST have matching **GET list** in the API (paginated) — do not ship create-only.
Forms MUST use `st.selectbox` / `st.multiselect` fed from list GETs — never `st.text_input("Site ID")` when `GET /api/v1/sites` exists.
After POST/PATCH success call `st.rerun()` so tables refresh.
**API-only apps** (`requiresStreamlit` false): implement FastAPI + tests only — do NOT create `ui/streamlit_app.py`.

**Step 0c — FR acceptance checklist (MANDATORY when prdPath is set)**
After Step 1a (reading the PRD), produce a numbered checklist mapping EVERY FR and NFR to its
implementation before writing any file. This is the FR equivalent of the route manifest:
  # FR checklist:
  # FR-1  | Service CRUD               | API: POST/GET/PATCH/DELETE /api/v1/services [services.py]
  # FR-2  | Runbook lifecycle           | API: POST/PATCH /api/v1/runbooks; guard: editor+ role
  # FR-13 | Role-gated UI access        | UI: login_form() gate in streamlit_app.py; role-gated tabs
  # NFR-4 | Auth on all endpoints       | guard: Depends(get_current_user) on every non-/health route
  # NFR-5 | Audit log                   | service: write to audit_log table on every state change

Rules — apply to every FR regardless of domain:
- Map EVERY FR/NFR to exactly one layer: API route, Depends() guard, Streamlit section/form,
  service method, or config setting.
- No FR may be left unmapped, and **"out of scope" is not a valid mapping by itself**. An FR/NFR
  that genuinely cannot be implemented (e.g. it depends on an external system this run has no
  access to) must be tagged `NOT IMPLEMENTED: <FR/NFR id> — <specific reason>` in this checklist,
  AND that exact line must be repeated in the `### not_implemented` section of the final handoff
  summary (Step 5b). Difficulty, time, or "keeping it simple" are never valid reasons — only a
  genuine external blocker is. A checklist row with no implementation and no NOT IMPLEMENTED tag
  is a bug, not an accepted scope reduction.
- UI-scope FRs (anything describing what a user sees, cannot see, or can access):
  implementation goes in streamlit_app.py — an API 403 alone does NOT satisfy a UI visibility FR
- Cross-cutting NFRs (auth, rate-limiting, audit, observability): name the file/layer that handles them
- After writing all files, revisit every line of this checklist and verify the implementation exists.
  Any unchecked FR is blocking — same rule as a missing route in the route manifest.

**Step 1 — understand requirements (read before writing a single line of code)**
1a. dev_read_file(prdPath) if set — read the full doc; locate topics by heading (not fixed numbers):
    overview/goals, user stories, **acceptance criteria**, core **data entities**, **NFRs**
    (auth, rate-limiting, observability). PRD section order varies per feature — search headings.
    After reading, produce the **Step 0c FR checklist** — write it out now (not later).
    Every FR and NFR in the PRD must appear in the checklist with its implementation layer named.
    Do not proceed to Step 2 until the checklist is written and every FR has a mapped layer.
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
    - `tests/conftest.py` — replace SCHEMA_NAME, match auth mode, add seed fixtures
    - `.env.example` — match config.py; KEY=value; DATABASE_URL= prefix. JWT vars MUST be named exactly JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_MINUTES (never JWT_SECRET, JWT_TTL_HOURS, or any other name) — the fixed auth code reads these exact names.
    - `ui/streamlit_app.py` (streamlit pattern) — tabs/forms only; keep HTTP helpers

    Files you GENERATE from scratch (business logic — not infrastructure):
    - `app/models/<entity>.py` — ORM models matching database-agent SQL
      (**JWT users:** password column attribute MUST be `password_hash` —
      same name as DDL — the users password column is ALWAYS `password_hash`.)
    - `app/routers/<domain>.py` — route handlers with business logic
    - `schemas/<domain>.py` — Pydantic request/response models
    - `app/services/bedrock_client.py` — copy from _template for B+/B++ patterns
    - `app/services/prompts.py` — app-specific system prompts
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
    - Foreign-key display names: when a list or detail response exposes a foreign-key id column
      (e.g. instructor_user_id, assignee_user_id) AND the referenced row has a human-readable field
      (name, title, username, label), ALSO include a sibling read-only field with that value, named
      <relation>_name (or <relation>_title where 'title' is the natural label). Populate it by joining
      or looking up the related row when building the response. Keep the original id field too.
      Example: a course response returns both instructor_user_id and instructor_name. This mirrors
      the shipped recipe-vault pattern (ingredient_id + ingredient_name). Skip this only when the
      design explicitly returns bare ids or the relation has no human-readable field.

      Worked example (FK display name):
      ```python
      # schema: expose BOTH the id and a human-readable name
      class CourseResponse(BaseModel):
          model_config = ConfigDict(from_attributes=True)
          id: str
          code: str
          title: str
          instructor_user_id: str       # keep the raw FK id
          instructor_name: str | None   # sibling display name from the related row

      # router: populate the name by joining the related row
      rows = db.execute(
          select(Course, User.full_name)
          .join(User, Course.instructor_user_id == User.id)
      ).all()
      return CourseListResponse(courses=[
          CourseResponse(**course.__dict__, instructor_name=name)
          for course, name in rows
      ])
      ```
    - status_code= on DECORATOR (not in comments): POST→201, DELETE→204 with response_model=None.
    - Postgres: sync SQLAlchemy SessionLocal + Depends(get_db) in EVERY DB-backed handler.
    - Auth per design **Rules** only — do NOT add JWT if Rules specify API-key only:
      * API-key → `Depends(require_api_key)` (public role check) or `Depends(require_role("role1","role2"))` in signature — never a second header
      * JWT bearer → `Depends(get_current_user)` / `require_role(...)` per RBAC table
      * Public routes → no auth dependency
      - Auth is PROVIDED as fixed infrastructure — do NOT create or edit app/security.py or app/dependencies.py, and NEVER create app/auth.py.
      JWT mode: import `from app.security import hash_password, verify_password, create_access_token`
      and `from app.dependencies import get_current_user, CurrentUser, require_role, DbSession`.
      Wire `Depends(get_current_user)` / `CurrentUser` and `Depends(require_role("role1","role2"))` onto routes per the RBAC table.
      Do NOT generate the auth router or auth schema — routers/auth.py and schemas/auth.py are FIXED (provided, copied verbatim, POST /api/v1/auth/login). Still generate the User ORM model (with columns id, username, password_hash, role). main.py's scaffold already pre-wires `app.include_router(auth.router, tags=["auth"])` with NO prefix, right next to health — do NOT remove it (its route path is already fully qualified as /api/v1/auth/login; adding a prefix would double it, and dropping the line breaks login entirely).
      API-key mode: import `from app.dependencies import require_api_key, CurrentUser, require_role, DbSession` — same names, same fixed file. There is no login route in this mode. Still generate the User ORM model (with columns id, token, role — see database-agent handoff). See "Auth — implement only what design Rules specify" below for the full, non-negotiable API-key rule.
    - List endpoints: match API surface response shape exactly:
      * Paginated page `{items, total, limit, offset}` when design specifies it
      * Bare `list[Schema]` only when design explicitly returns an array
      * Always include pagination query params the design documents (limit/offset or skip/limit)
    - ORM models matching database-agent SQL exactly (column names, types, nullable, FKs).
    - Workflow transitions (status/assign/archive/return/...): implement ONE route — the
      dedicated `/{id}/<action>` sub-path. Do NOT also add a bare `PATCH/PUT /{id}` route that
      takes the same request schema as the dedicated action route — see "Never ship a bare-id
      update route that clones a dedicated action route" below; it's a hard-fail validation check.
3b. Implement EVERY business rule stated in design **Rules** and PRD **acceptance criteria** — these
    are mandatory, not optional polish, and are NOT satisfied by a plain CRUD handler with no guard.
    This explicitly includes, whenever the design/PRD states them: status/state transitions and which
    transitions are legal, capacity/quota limits, permission/role gating beyond basic auth, sequencing
    or ordering rules (e.g. "X must happen before Y"), and validation tied to a specific acceptance
    criterion. Do not implement a weaker version of a stated rule (e.g. a status column with no
    transition guard when the design specifies which transitions are legal) and do not skip a rule
    because it takes more code than a plain CRUD handler.
    Return error shapes consistent with the API surface error contract.
    **Safety valve:** if a specific rule genuinely cannot be implemented (e.g. it depends on an
    external system this run has no access to), do not implement a silent no-op or a weaker
    substitute — add `NOT IMPLEMENTED: <rule as stated> — <specific reason>` to the `### not_implemented`
    section of the handoff summary (Step 5b) instead.
3c. MongoDB: motor async. Never SQLAlchemy for MongoDB collections.
3d. Write **baseline smoke tests** (one happy-path per route; 404/422 where design specifies).
    conftest.py MUST set DATABASE_URL env var BEFORE importing from app — see test section.
    Mock get_bedrock_client at import site, not definition site.
    **JWT + db/sql/*seed*.sql:** add `tests/test_seed_bcrypt.py` (copy from
    `target-apps/_template/tests/test_seed_bcrypt_reference.py`). conftest `hash_password(...)`
    MUST use the **same plaintext** documented in the seed SQL comment — never a different password.
    Passing pytest without test_seed_bcrypt.py is a false green for RDS login.
    When seed SQL uses `__BCRYPT_PLACEHOLDER__`, README **Seed Users** (or **Demo accounts**) section:
    - Table: username/email | password | role — use the plaintext from the seed SQL comment / HANDOFF.
    - Do **not** mention `__BCRYPT_PLACEHOLDER__`, `materialize_seed_passwords.py`,
      `apply_sql_to_rds.py`, seed-apply notes, or other pipeline internals — README is for app
      users/dev setup, not the SDLC pipeline.

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
    `cd target-apps/<app>`) — never bare `cd ui` without that prefix. When React UI
    exists, Terminal 2 is `cd target-apps/<app>/frontend` (sibling of the API tree —
    never nest under a backend folder). On the published apps repo the same trees are
    `<app>/backend` + `<app>/frontend` (gitlab-agent rewrites paths). Split **Terminal 1 (API)**
    and **Terminal 2 (UI)** when Streamlit or a second process is required; Terminal 2 repeats
    `cd target-apps/<app>`, venv activate, then subdir (e.g. `cd ui`). README MUST use **separate**
    **PowerShell (Windows)** and **Bash** code blocks (not bash-only with a comment). Windows venv:
    `.\\.venv\\Scripts\\Activate.ps1` — never `source` as the only activate instruction. Copy .env:
    Windows `Copy-Item .env.example .env`; bash `cp .env.example .env`. Edit DATABASE_URL +
    POSTGRES_SCHEMA + auth secret; `uvicorn app.main:app --reload --port 8000`; pytest command.
    **Uvicorn reload:** if `.venv/` is under the app dir, document `--reload-exclude '.venv'` or
    run without `--reload` — otherwise pip install triggers endless reload and Streamlit ReadTimeout.
    streamlit pattern: document UI URL (http://localhost:8501) and `streamlit run` in
    Terminal 2 block only. Postgres: `.env.example` must show `postgresql+psycopg://...?sslmode=require`; note URL-encoding
  passwords (# → %23). Include a pytest command if tests exist; do **not** explain that tests use
    SQLite / in-memory DB — that is an implementation detail, not user docs.
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

  FR completeness (MANDATORY when prdPath was read — same weight as route manifest):
  - Step 0c FR checklist fully covered — every FR/NFR has a verified implementation
  - No FR left unmapped or deferred without explicit "out of scope" justification in open_questions
  - UI-scope FRs (access control, role-gated views, login screens): confirmed in streamlit_app.py, not just API layer
  - Cross-cutting NFRs (auth, audit, rate-limiting): confirmed in the named file/layer from the checklist

  Route completeness:
  - Route manifest fully covered — every METHOD /path from API surface has a handler
  - count(app/routers/*.py minus __init__.py) == count(include_router calls in main.py)
  - Every subdirectory (models/, routers/, schemas/) has __init__.py
  - status_code=201 on every @router.post() decorator; status_code=204 on every DELETE
  - Every DB-backed route: db: Session = Depends(get_db) in signature
  - Every auth-required route uses the auth mode from Rules (API-key OR JWT — not both unless required)
  - List routes match API surface shape (page object OR list[T]) with documented pagination params
  - No bare `PATCH/PUT /{id}` route shares a request schema with a dedicated `/{id}/<action>`
    route on the same resource — that's a redundant clone route, not a general update

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
  - When seed SQL uses `__BCRYPT_PLACEHOLDER__`: README lists demo credentials only (no placeholder,
    no invented second secret). For API-key auth, the value pasted into Streamlit/Swagger **must be
    the seed-comment password** (same string hashed into `api_keys` / `token_hash`)
    apply_sql/materialize script names, seed-apply notes, or SQLite-test notes); password matches
    seed SQL comment exactly

  UI parity (Pattern C / requiresStreamlit only — skip when API-only):
  - `dev_validate_app` must report `UI_PARITY OK`
  - Every design §4 collection GET implemented in FastAPI AND called from `ui/streamlit_app.py`
  - Every POST-on-collection has matching GET list (e.g. POST+GET `/api/v1/sites`)
  - No raw UUID `st.text_input` when a list GET exists for that entity
  - API-only: no `ui/` directory unless deliveryProfile requires Streamlit

**Step 5b — VALIDATE (mandatory — do NOT skip or declare success early)**
After all files are written and the checklist above is done:
  1. Call `dev_validate_app(service=targetApp, run_pytest=True)` — must end with
     `VALIDATION PASSED` in the tool output. Fix every failure and call again.
  2. **`### not_implemented` section — mandatory in every handoff summary, no exceptions.**
     If the Step 0 route manifest, Step 0c FR checklist, and Step 3b business rules were all fully
     covered, write exactly:
       ### not_implemented
       None.
     If ANY route, FR/NFR, or business rule was genuinely not implementable, list every one here,
     one line per item, reusing the exact tags from Step 0/0c/3b:
       ### not_implemented
       NOT IMPLEMENTED: DELETE /api/v1/widgets/{id} — design requires calling an external
         inventory system this run has no credentials for.
     **Do not** claim the app is "fully functional," "complete," or fully covers the design/PRD when
     this section lists any items — state the gap explicitly instead of a general success claim.
  3. **Never** tell the user the app is "fully functional" if import or pytest failed.
     SEED_BCRYPT: non-blocking when seed SQL uses `__BCRYPT_PLACEHOLDER__` with a documented
     password comment (pipeline materializes hashes via `apply_sql_to_rds.py`). Blocking when
     a real bcrypt hash in the seed SQL doesn't match the documented password. Either way, when
     `SEED_BCRYPT NOTE` appears in validation output, your handoff summary MUST include:
     "⚠ Run `python scripts/apply_sql_to_rds.py --target-app <app>` (or
     `python agents/_shared/materialize_seed_passwords.py --target-app <app>`) before
     testing RDS login — seed passwords are not active until this runs."
  4. Common fixes the validator catches:
     - `CurrentUser = Depends()` → use `current_user: CurrentUser` only (no `= Depends()`)
     - Parameter order: `CurrentUser` / `DbSession` before `Query(default=...)` params
     - SQLite Date columns: use `date(2024, 1, 1)` in test fixtures, not `"2024-01-01"` strings
     - RDS_PARITY FAILED: fix TimestampTZ ORM + coerce_iso_datetime validators, seed/schema nullability
       (optional DDL columns → `Mapped[T | None]` + optional Pydantic fields), or seedCredentials /
       users INSERT layout for materialize (see `agents/_shared/validate_rds_parity.py`)
     - UI_PARITY FAILED: missing design §4 routes, POST without GET list, Streamlit not calling
        collection GETs, raw UUID text_input when list APIs exist, or double-slash API paths
        like `/api/v1/admin//status` (see validate_ui_parity.py — autofix collapses `/api/...` literals)
      - DUPLICATE_ACTION_ROUTE FAILED: a bare `{id}` PATCH/PUT route takes the same request schema
        as a dedicated `{id}/<action>` route — delete the bare-id clone (or give it its own distinct
        general-update schema if the design truly needs both a general update and an action route)
      - AUTH_MODE_FILES FAILED: dependencies.py, the JWT trio, or main.py don't match authMode —
        call dev_scaffold(service, pattern="B", force=True) to re-copy the right variant, and remove
        any auth router import/registration in main.py when authMode is api-key
      - API_KEY_ROUTE_USAGE FAILED (api-key mode only): no route applies Depends(require_api_key) —
        wire it onto every route design Rules require auth on
      - AUTH_HEADER_NAMES FAILED (api-key mode only): design names a header (e.g. X-Admin-Key) that
        nothing in app/auth.py or app/dependencies.py reads — add an APIKeyHeader-based dependency
        for that exact header in app/auth.py; never substitute require_api_key's X-API-Key for it

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
_run_context: dict[str, Any] | None = None

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
app/dependencies.py  [SCAFFOLD — do not edit, fixed auth]
app/security.py      [SCAFFOLD — do not edit, fixed auth]
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
`app/services/ingestion.py` MUST dispatch on the upload's filename extension and support every
format the brief/UI actually accepts (at minimum pdf, docx, and plain text — txt/md/log) — never
hard-code a single-format parser (e.g. PDF-only via pypdf) and let it silently swallow other
extensions. Raise a typed `UnsupportedDocumentTypeError` for anything with no extractor so the
failure has a name and a message, never a bare `except Exception`.
The `documents` table MUST carry an explicit ingestion status (`ingestion_status`:
processing/ready/failed, plus `ingestion_error` text) distinct from `active_version_id` —
otherwise "still processing" and "permanently failed" are indistinguishable to the user, and a
failed upload looks identical to one still ingesting, forever, with no visible reason.
The query router MUST actually call `pgvector_retriever.py`'s retriever (via a `get_retriever`
FastAPI dependency, mirroring `get_bedrock_client`) and filter by `CONFIDENCE_THRESHOLD` — never
fall back to "grab the first N chunks in table order" and never gate the "insufficient
information" fallback on "do any chunks exist for this document" alone. That check must be
per-question relevance (retrieved score >= confidence_threshold), or every question — including
irrelevant ones like "hi" — gets the identical canned answer whenever a scoped document happens to
have zero or low-relevance chunks. Adapt the retriever's illustrative column names (`doc_id`,
`page`, `text`, `collection_id`) to the ACTUAL schema you generated in db/sql/*.sql — do not leave
them as placeholders that don't match real columns; a query router built on a retriever with
guessed columns will throw at runtime.
Because pgvector's `<=>` operator and `vector` cast have no SQLite equivalent, the retriever must
be dependency-injected (never instantiated inline in the router) so `tests/test_chat_rag.py` can
override it with a fake and stay off a live Postgres/pgvector connection.
requirements.txt adds: pypdf, python-docx, pgvector, boto3.
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
list APIs; call `st.rerun()` after mutations. Fetch catalog lists once per tab/view — never `_get()`
inside a `for row in items` loop (causes API timeouts). `dev_validate_app` enforces UI_PARITY when Streamlit is required.
**Streamlit API paths (CRITICAL — live ALB 404s):** Paths passed to `_get`/`_post`/`_patch`/`_delete`
MUST be exact FastAPI routes with **single** slashes — never concatenate a trailing `/` on a prefix
with a leading `/` on a segment. Wrong: `"/api/v1/admin//status"`, `"/api/v1//query"`.
Right: `"/api/v1/admin/status"`, `"/api/v1/query"`. FastAPI returns `{"detail":"Not Found"}` for `//`
paths while login/`/health` still work — looks like ALB breakage but is a UI path bug.
Keep the scaffold `_api_url()` helper (collapses accidental `//` at runtime); do not remove it.
`dev_validate_app` auto-fixes `/api/...` string literals with `//` and fails UI_PARITY if any remain.
**Streamlit width API:** Never `use_container_width=True/False` (deprecated/removed). Never
`width=0` / `width=False` (StreamlitInvalidWidthError on Streamlit 1.41+). Use only
`width="stretch"` for full-width dataframes/buttons, or `width="content"` to fit content.
**Streamlit string literals:** Never put a raw newline inside `"..."` / `f"..."` quotes.
Use `"line1\\nline2"` escapes or adjacent string concatenation on one logical statement.
Broken multiline f-strings pass some editors but crash live UI (`SyntaxError: unterminated f-string`)
while `_stcore/health` can still return 200 — CI looks green, browser shows Script execution error / 502.
**Arrow-safe dataframes:** In `st.dataframe`/`st.table` data, never mix string placeholders
("—", "N/A", "") into numeric columns — pass `None` for missing values (Arrow rejects mixed-type
columns). Placeholders belong in display formatting (`st.column_config.NumberColumn(format=...)`)
or single-value widgets like `st.metric`, never in the DataFrame itself.
README: **Terminal 2** — separate **PowerShell (Windows)** and **Bash** blocks: `cd target-apps/<app>`,
`.\\.venv\\Scripts\\Activate.ps1` (Windows) or `source .venv/bin/activate` (bash), `cd ui`, then
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


_JWT_MAIN_PY_SECTION = """\
### main.py — register EVERY router

The scaffolded main.py already pre-wires health and auth (do not remove either
— see target-apps/_template/app/main.py). Add every domain router below them.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.routers import health, items, auth   # import every router module

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: CREATE EXTENSION vector; mkdir UPLOAD_DIR; etc.
    yield

app = FastAPI(title="My Service", lifespan=lifespan)
app.include_router(health.router, prefix="/health")
app.include_router(auth.router, tags=["auth"])
app.include_router(items.router, prefix="/api/v1/items", tags=["items"])
```

Pre-handoff: count `.py` files in `app/routers/` minus `__init__.py` ==
count `include_router` calls in `main.py` (auth and health both count — they're
pre-wired, not something you add). If they differ, fix main.py now."""

_API_KEY_MAIN_PY_SECTION = """\
### main.py — register EVERY router (api-key mode — no auth router)

The scaffolded main.py already pre-wires health only (do not remove it — see
target-apps/_template/app/main_apikey.py, the api-key-mode reference). There is
no login route and no auth router in this mode — do NOT add
`from app.routers import auth` or `app.include_router(auth.router, ...)`; routes
that need auth use `require_api_key` from `app/dependencies.py` directly. Add
every domain router below health.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.routers import health, items   # import every router module — no auth router here

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: CREATE EXTENSION vector; mkdir UPLOAD_DIR; etc.
    yield

app = FastAPI(title="My Service", lifespan=lifespan)
app.include_router(health.router, prefix="/health")
app.include_router(items.router, prefix="/api/v1/items", tags=["items"])
```

Pre-handoff: count `.py` files in `app/routers/` minus `__init__.py` ==
count `include_router` calls in `main.py` (health counts — it's pre-wired, not
something you add; there is no auth router to count in this mode). If they
differ, fix main.py now."""


def _build_system_prompt(ctx: dict[str, Any] | None = None) -> str:
    keys = _select_pattern_keys(ctx)
    section = _compose_pattern_section(keys)
    if keys:
        print(
            f"[developer-agent] System prompt: pattern {'+'.join(keys)} only "
            "(DEVELOPER_AGENT_AUTO_PATTERN=1)",
            file=sys.stderr,
        )
    auth_mode = str((ctx or {}).get("authMode") or "jwt").strip().lower()
    main_py_section = _API_KEY_MAIN_PY_SECTION if auth_mode == "api-key" else _JWT_MAIN_PY_SECTION
    rendered = _DEVELOPER_SYS_PROMPT_TEMPLATE.replace("{{PATTERN_LAYOUTS}}", section.rstrip())
    return rendered.replace("{{MAIN_PY_SECTION}}", main_py_section)


_DEVELOPER_SYS_PROMPT_TEMPLATE = """\
You are the Developer Agent for the SDLC Agentic AI Platform. You are the fifth agent in a
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
| `db/sql/`, `databaseHandoffPath` | database-agent | Read only |
| `.venv/`, `node_modules/` | Human / local | **Never write** |

## MVP phase scope

- **In scope:** Python 3.12 + FastAPI + Pydantic v2 under `target-apps/<service>/`.
- **Streamlit UI (Pattern C):** REQUIRED when `deliveryProfile.requiresStreamlit` is true in Context,
  or PRD section 11 / input brief requires Streamlit — even if design.md Stack omitted it.
  Place at `ui/streamlit_app.py`; call API over HTTP; add `streamlit` to `ui/requirements.txt`;
  README documents Terminal 1 (uvicorn) + Terminal 2 (`streamlit run ui/streamlit_app.py`).
  Streamlit widgets: use `width="stretch"` / `width="content"` — never `use_container_width`
  and never `width=0` (crashes live UI on Streamlit 1.41+).
  **UI scope:** Wire Streamlit to design §4 **collection GET** routes and role-specific views — NOT every
  internal/admin route needs a screen, but browse/create flows from the PRD MUST be usable without pasting UUIDs.
- **API-only (Pattern B/B+/B++ without Streamlit):** FastAPI routes + pytest only — no `ui/` folder.
  `dev_validate_app` skips Streamlit checks when `requiresStreamlit` is false.
- **JWT vs API key:** Match design **Rules** and PRD — Streamlit must use the same auth mode
  (Bearer JWT from `POST /api/v1/auth/login`, or `X-API-Key` header when API-key auth).
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
| `productBrief` | Context JSON | Compact product orientation when prdPath is absent |
| `diagramPaths` | Context JSON | PNG — do not parse |

## Language and framework — design tech stack is the authority

Default to Python/FastAPI only when tech stack is absent (add to open_questions then).

## Seed credentials — placeholders only (pipeline materializes on RDS)

If `HANDOFF.md` has `### seedCredentials` or seed SQL uses `'__BCRYPT_PLACEHOLDER__'`, **do NOT invent bcrypt strings** — the LLM cannot compute real hashes.

1. Optionally copy `target-apps/_template/scripts/seed_dev_users.py` via `dev_scaffold` and set `_CREDENTIALS` from HANDOFF (local re-seed only).
2. **Do NOT** tell users to run `seed_dev_users.py` as a required setup step — `scripts/apply_sql_to_rds.py` **automatically** calls `materialize_seed_passwords.py` after seed SQL.
3. README "Setup": document seed login emails/passwords from HANDOFF in a **Demo accounts** table
   only. Do not mention seed-apply scripts, placeholders, materialize steps, or that "logins work
   after DB seed" — the pipeline handles that; app README is for running the service and demo logins.
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
| M2M / junction `secondary=` | Define the association `Table("book_authors", Base.metadata, ...)` **once** (usually in one of the two model files). BOTH sides MUST use the **same Table object**: `relationship("Book", secondary=book_authors, back_populates="authors")` — NEVER `secondary="book_authors"` (string). String secondary fails mapper init when the other file loads first (`InvalidRequestError: mappers failed to initialize` / `name 'book_authors' is not defined`), and list/CRUD routes 500 while `/health` still looks green. Import the Table into the other model file if needed (`from app.models.book import book_authors`). |
| Conditional aggregates | `case` is a top-level SQLAlchemy construct, NOT a `func` member. `func.case((cond, 1), else_=0)` raises `OperationalError: no such function: case` at runtime. Correct: `from sqlalchemy import case` then `case((cond, 1), else_=0)`. Same for `cast`, `null`, `true`, `false` — all top-level imports, not `func` members. |
| `ARRAY(PG_UUID(...))` column assigned a request's `list[str]` | Postgres allows an implicit `varchar → uuid` cast for a single scalar, but refuses it for arrays — binding a plain `list[str]` into a `uuid[]` column raises `DatatypeMismatch: column "..." is of type uuid[] but expression is of type character varying[]`. SQLite tests pass anyway (no type enforcement), so this only surfaces on real RDS, exactly like the other rows in this table. Always convert to `uuid.UUID` objects at the router before assigning: `[uuid.UUID(x) for x in body.some_ids] if body.some_ids else None`. |

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
| Multi-line strings | A single-quoted or double-quoted string literal MUST NOT contain a literal line break — that is a `SyntaxError`. Use an explicit `\n` inside the quotes (`"line one\nline two"`) instead of pasting a real newline into the literal. Applies to error messages, LLM prompts, and any other multi-line text — including inside test files and fixtures |
| RAG chunk insert without embedding | Every `document_chunks`-style INSERT into a pgvector `embedding` column MUST be preceded by an actual `bedrock.invoke_embed(chunk_text)` call for that exact chunk — never insert a chunk row with `embedding` omitted, `None`, or a placeholder. Postgres raises `DatatypeMismatch` (vector column, non-vector value) if this is skipped, and the upload silently never reaches "ready" |
| Background-task exception handler that re-commits | If a background task's `except` block itself calls `session.commit()` (e.g. to persist `status="failed"`), call `session.rollback()` FIRST. A DB-level error on the first commit leaves the session/transaction poisoned — a second commit on the same session raises too, the whole exception escapes uncaught, and the record is left stuck at its prior status (e.g. "processing") forever with no error surfaced |

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
| `Form(...)` / `File(...)` / `UploadFile` route params | FastAPI raises `RuntimeError: Form data requires "python-multipart" to be installed` **at import time** — the whole module fails to load, so SQLite pytest never even reaches the route. On ECS this kills the essential API container at startup and crash-loops the task forever (deploy health check never passes). | The moment any router uses `Form(...)`, `File(...)`, or `UploadFile`, add `python-multipart>=0.0.9` to `requirements.txt` immediately — do not wait until testing surfaces it. |
| `import app.models` + bare `app` name | `from app.main import app` then `import app.models` rebinds `app` to the **package**; `app.dependency_overrides` raises `AttributeError` on every test using the `client` fixture | Always `from app.main import app as fastapi_app`; use `fastapi_app.dependency_overrides` and `TestClient(fastapi_app)`. The golden conftest_reference.py already includes `import app.models` — do not re-add it under a bare `app` name. |
| Streamlit `use_container_width` / `width=0` | Deprecated/invalid; Streamlit 1.41+ raises `StreamlitInvalidWidthError` on live UI | Never `use_container_width=True/False` and never `width=0`. Use `width="stretch"` (full width) or `width="content"` on `st.dataframe`, `st.button`, `st.form_submit_button`, `st.download_button`, etc. |
| Streamlit `_get("/api/v1/...//...")` double slash | FastAPI 404 `{"detail":"Not Found"}` on Status/Audit/Query while login/`/health` still work — looks like ALB failure | Paths must match routes exactly with single slashes (`/api/v1/admin/status`). Keep scaffold `_api_url()`; never invent `admin//status` or `v1//query`. `dev_validate_app` autofixes `/api/...` literals. |
| API-key demo secret ≠ seed password | README invents `ADMIN_KEY_DEV` / random tokens while seed SQL bcrypt-hashes the seed-comment password into `api_keys` / `token_hash` — live UI 401s | When auth is `X-API-Key` and seed uses `__BCRYPT_PLACEHOLDER__`, README **Demo credentials** MUST tell the tester to paste the **same plaintext** as `-- Password for all seed users: "..."` (e.g. `ExpenseTest123!`). Do not invent a second key name unless that exact string is what was hashed. |
| SHA-256 API key seed fakes | Seed inserts `sha256_foo_001` into `key_hash` while app does `sha256(raw).hexdigest()` lookup — every login 401s | Seed MUST use `__SHA256_PLACEHOLDER:<label>__` + `-- API key for <label>: "demo-…"`; README / `.env.example` MUST list those exact plaintext keys. Never invent fake `sha256_*` tokens or a different README key. |

When writing `tests/conftest.py`, COPY `_template/tests/conftest_reference.py` via
`dev_read_file("target-apps/_template/tests/conftest_reference.py")` then `dev_write_file` as
`tests/conftest.py`. Only change: replace SCHEMA_NAME, choose API-key vs JWT auth fixtures,
add app-specific seed fixtures. Do NOT rewrite the engine, session, or UUID-patch logic.

## Auth — implement only what design Rules specify

| Rules say | Implementation |
|-----------|----------------|
| API-key (`X-API-Key`) | `require_api_key` / `CurrentUser` / `require_role(...)` from fixed `app/dependencies.py`; never a second header |
| JWT bearer + roles | Import `get_current_user` / `require_role` from fixed `app/dependencies.py` (do not write them); apply on routes per RBAC; bcrypt hashes in DB when users table exists |
| Public read, protected write | Apply auth dependency only on write routes listed in API surface |
| No auth | Do not add JWT, API-key middleware, or fake secrets |

Never add JWT scaffolding when Rules specify API-key only. Never add API-key when Rules specify JWT only.

**Public routes stay public — do not add auth "just to be safe."** When the PRD/brief's
persona-auth table or the design's API surface Notes column marks a route anonymous /
public / no-auth (a common pattern: list/read routes like `GET /desks`, `GET /availability`
are public while writes and admin routes are gated), that route MUST have ZERO auth
dependency — not `require_api_key`, nothing. Check the PRD/brief's auth table for
per-route exceptions even when the design doc's compact "Auth:" Rules line only states
the general shape without repeating which specific routes are exempt — the design doc's
summary line can compress away an exception the brief/PRD stated explicitly; the more
detailed source wins. Defaulting every route to some credential when in doubt is the
wrong instinct in api-key mode — it silently breaks anonymous access design explicitly
required.

### API-key mode — ONE fixed auth model, hardcoded, no exceptions

There is exactly one header, ever: `X-API-Key`. There is no `X-User-Id`, no
`X-User-Token`, no `X-Admin-Key`, no second header of any kind, regardless of
what the design doc's Rules section says about "employee vs admin" or
"two-tier" auth. Role differences described in the design are RBAC — express
them with `require_role(...)`, never with a second credential/header.

`require_api_key`, `CurrentUser`, and `require_role(*roles)` all live in the
FIXED, write-guard-protected `app/dependencies.py` (do not edit it, do not
reuse its names for something else). `require_api_key` already resolves the
caller's identity and role by looking the `X-API-Key` value up in the `users`
table (`token` column) — that lookup is infrastructure, not something you
implement:

```python
from app.dependencies import CurrentUser, require_role, DbSession

@router.get("/api/v1/items")
def list_items(current_user: CurrentUser, db: DbSession): ...

@router.post("/api/v1/items", status_code=201)
def create_item(body: ItemCreate, current_user: Annotated[dict, Depends(require_role("manager", "admin"))], db: DbSession): ...
```

Hard rules (each is a validation gate — `validate_no_invented_auth_headers`
fails the build on any violation):

1. **Never create `app/auth.py`.** In api-key mode this file does not exist —
   the write-guard rejects it outright. There is no dependency to add outside
   `app/dependencies.py`.
2. **Never declare a second `APIKeyHeader(...)` scheme or a bare
   `Header(alias="X-...")` auth parameter anywhere** — not in routers, not in
   a helper module. Any header-reading code outside the fixed
   `app/dependencies.py` is an invented auth scheme and fails the build, even
   if the design doc's prose suggests a named header like "X-Admin-Key".
3. Every route that needs a specific role gates with
   `Depends(require_role("role1", "role2"))`; every route that just needs
   *some* authenticated caller gates with `Depends(require_api_key)` /
   `CurrentUser`. Both come from the same header, the same table lookup —
   only the role check differs.

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

When design stores **SHA-256 digests** in `api_keys.key_hash` (DB lookup, not env compare),
hash the header and SELECT by digest. Seed must use `__SHA256_PLACEHOLDER:<label>__` +
`-- API key for <label>: "…"` (see `_template/db/reference/sha256_api_keys_seed_reference.sql`).
README / `.env.example` demo keys MUST be those same plaintext strings — never invent a
second set of keys, and never invent fake `sha256_*` seed tokens.

### Router prefix vs route path — no double prefix

The final URL is `app.include_router(prefix=...) + @router.get(...)`. Concatenating
PREFIX STANDARD: every domain router MUST be registered with the /api/v1 prefix (each domain at prefix="/api/v1/<domain>"). The auth router is already fully qualified (/api/v1/auth/login) and comes pre-wired in main.py's scaffold with NO prefix: app.include_router(auth.router, tags=["auth"]) — do not remove it or add a prefix to it. Only health uses bare "/health".
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

### Never ship a bare-id update route that clones a dedicated action route

When a resource has a workflow transition (status, assignment, archive, return, etc.),
implement it as **one** route: the dedicated sub-path action (`PATCH/PUT /{id}/status`,
`/{id}/assign`, `/{id}/archive`, ...). Do **not** also add a general `PATCH/PUT /{id}`
route that takes the *same request schema* as the dedicated action — that is a
redundant clone, not a real general-update endpoint, and it lets callers bypass the
route named for the transition while doing the exact same thing under a different,
ambiguous URL.

```python
# wrong — both routes take StatusUpdate and do the identical transition; the bare
# PATCH /{id} is a dead-weight clone of PATCH /{id}/status, not a general update
@router.patch("/api/v1/findings/{id}")
def patch_finding(id: str, body: StatusUpdate, ...): ...

@router.put("/api/v1/findings/{id}/status")
def update_finding_status(id: str, body: StatusUpdate, ...): ...

# right — only the dedicated action route exists
@router.put("/api/v1/findings/{id}/status")
def update_finding_status(id: str, body: StatusUpdate, ...): ...
```

If the design genuinely calls for both a general field update (title, description,
assigned_to, ...) **and** a dedicated status/action transition, give the general
route its own distinct request schema (e.g. `FindingUpdate` with editable fields,
never `StatusUpdate`) — never reuse the action route's schema on the bare `{id}`
route. `dev_validate_app` enforces this with a hard-fail
`DUPLICATE_ACTION_ROUTE` check; do not add a second route around it.

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
CurrentUser = Annotated[dict, Depends(get_current_user)]  # returns {"user_id","role"}

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
- JWT fields (jwt_secret_key, jwt_algorithm, jwt_expire_minutes) are active in config.py by default; do not comment them out or rename them
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

{{MAIN_PY_SECTION}}

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
3. Add app-specific seed fixtures (import from `app.models.*` inside fixtures — do NOT add another `import app.models` if already present)
4. Import `hash_password`, `create_access_token` etc. from the app's security module

**Critical rules (regardless of reference):**
- `os.environ.setdefault(...)` for ALL config vars BEFORE any `from app.*` import
- Always `from app.main import app as fastapi_app` — never bare `from app.main import app` at module level
- `import app.models` (already in reference) binds local name `app` to the **package** — use only `fastapi_app` for TestClient and dependency_overrides
- Never create `TestClient(fastapi_app)` at module level — always inside the `client` fixture
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
- CORS: app/main.py MUST register `CORSMiddleware` (from `fastapi.middleware.cors`)
  right after the `FastAPI()` call — every generated app ships a browser frontend
  that sends a custom header (`X-API-Key` or `Authorization`), so the browser
  always preflights with an OPTIONS request first. Without CORSMiddleware,
  Starlette 405s that OPTIONS request and the real call never reaches the API —
  the frontend just shows "failed to load", with no other symptom. Read
  `allow_origins` from `settings.cors_origins` (add a `cors_origins: list[str] =
  Field(default_factory=lambda: ["*"], alias="CORS_ORIGINS")` field to
  app/config.py's Settings), set `allow_credentials=True`, and set both
  `allow_methods` and `allow_headers` to `["*"]` so the preflight's
  `Access-Control-Request-Headers` is always satisfied. Copy the exact block from
  `target-apps/_template/app/main.py` (jwt mode) or `main_apikey.py` (api-key
  mode) — do not improvise it. `dev_validate_app` hard-fails the build if this
  is missing (see `validate_cors_configured`).
- Write ONLY under `target-apps/`. Do not modify `db/sql/`. Do not claim Jira/GitLab actions.

## Pre-handoff self-review (mandatory after all writes, before summary)

1. `dev_list_tree(targetApp)` — verify file list is minimal and complete.
2. Route manifest check: every METHOD /path from API surface is handled.
3. Router count check: count(routers/*.py - __init__.py) == count(include_router in main.py).
4. Every subdirectory has `__init__.py`.
5. Every POST has status_code=201 on decorator; every DELETE has status_code=204.
6. Every DB-backed route has Depends(get_db); auth routes use Rules-specified deps (API-key or JWT).
7. List routes match API surface (page object or list[T]) with documented pagination params.
8. conftest.py sets env before app import; uses `fastapi_app` alias; no module-level TestClient.
9. No circular imports: schemas → nothing from app/; models → enums only.
9b. app/main.py registers `CORSMiddleware` right after `FastAPI()`, reading
    `allow_origins=settings.cors_origins`; app/config.py's Settings has a
    `cors_origins` field. Copied from `_template/app/main.py` /
    `main_apikey.py`, not hand-rolled.
10. requirements.txt matches actual imports — no psycopg2-binary, no missing packages.
11. .env.example has every env var config.py reads; .gitignore has .env and .venv/.
    When `deliveryProfile.requiresReact` is true (the app has a `frontend/`), README.md MUST
    also include a `## Frontend (React UI)` section, placed AFTER the backend run steps,
    containing exactly:
    - Install/run: `cd frontend`, `npm install`, `npm run dev`.
    - The dev server runs at http://localhost:5173 — this origin MUST be allowed by CORS_ORIGINS.
    - **Port alignment (critical):** the frontend calls the API at http://localhost:8000 by
      default (`VITE_API_URL`). The backend MUST run on port 8000, OR the user must set
      `VITE_API_URL` in `frontend/.env.local` to match the backend's port. State this
      explicitly — a mismatch causes silent CORS/preflight failures that surface as a
      misleading "invalid API key" error, not an obvious network error.
    - Browser login: for api-key apps, the login screen is a single API-key field — paste one
      of the seed tokens from the Demo Accounts/Seed Users table above (e.g. the admin token
      for full access, including the Users screen); for JWT apps, log in with a seeded
      username/password from that same table.
    - Role-gated UI note: admin-role users see admin-only screens (e.g. user management);
      lower roles do not — this reflects the same role table documented above.
    Reference the existing Demo Accounts/Seed Users table — never duplicate seed tokens/passwords
    in this section. Backend-only apps (no `frontend/`) MUST NOT include this section.
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
21. Many-to-many / junction tables: never use `relationship(..., secondary="table_name")` strings. Define `Table(...)` once and pass that object on both `relationship(..., secondary=junction_table, back_populates=...)` sides. Host validation runs `configure_mappers()` and will fail the step if string secondary or broken M2M wiring is present.
"""

# Backwards-compat alias: legacy "all patterns" prompt. Prefer _build_system_prompt(ctx).
DEVELOPER_SYS_PROMPT = _build_system_prompt(None)


def _resolve_repo_path(relative_path: str, *, write: bool) -> Path:
    raw = relative_path.strip().replace("\\", "/")
    if not raw:
        raise ValueError("path is required")
    # Normalize whitespace around path segments (LLM-authored paths occasionally carry
    # a stray space, e.g. "_template /scaffold-manifest.json") — an un-stripped segment
    # defeats exact-match guards downstream (_validate_dev_write_path's "_template" check)
    # and previously let a write land as a bogus top-level runs/<runId>/_template /... key.
    raw = "/".join(seg.strip() for seg in raw.split("/"))
    candidate = (
        (_REPO_ROOT / raw).resolve()
        if not Path(raw).is_absolute()
        else Path(raw).resolve()
    )
    if not str(candidate).startswith(str(_REPO_ROOT.resolve())):
        raise ValueError(f"path must stay inside repo: {relative_path}")
    if write:
        template_root = (_TARGET_APPS / "_template").resolve()
        if candidate == template_root or template_root in candidate.parents:
            raise ValueError(
                "target-apps/_template is read-only; use dev_scaffold to copy from it"
            )
        under_target_apps = str(candidate).startswith(str(_TARGET_APPS.resolve()))
        if not under_target_apps:
            raise ValueError("writes only allowed under target-apps/")
        return candidate
    allowed = (
        any(str(candidate).startswith(str(p.resolve())) for p in _READ_PREFIXES)
        or candidate == _REPO_ROOT.resolve()
    )
    if not allowed:
        raise ValueError(f"read not allowed for path: {relative_path}")
    return candidate


def _cloud_artifact_rel(local_rel: str) -> str:
    """Rewrite local ``target-apps/<slug>/...`` to cloud ``<slug>/...`` for S3 keys."""
    if not _is_cloud_store():
        return local_rel
    normalized = local_rel.replace("\\", "/")
    if normalized.startswith("target-apps/"):
        return normalized[len("target-apps/"):]
    return normalized


def _service_dir(service: str) -> Path:
    return _TARGET_APPS / slugify(service)


def _ensure_service_exists(service: str) -> Path:
    """Ensure target-apps/<service>/ exists. Layout is design-driven — no auto-copy."""
    requested = service.strip().replace("\\", "/").strip("/").casefold()
    if requested in {"_template", "template", "target-apps/_template"}:
        raise ValueError(
            "target-apps/_template is a read-only scaffold source, not a target service"
        )
    dest = _service_dir(service)
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _clear_app_tree(target_app: str) -> None:
    """Empty target-apps/<app>/{app,schemas,tests,.env} before a full regeneration.

    developer-agent always rewrites the complete app from the design/PRD on every
    orchestrator-driven run (DEV_TASK_DB/DEV_TASK_NO_DB always mean full regen —
    see _step_developer in sdlc_pipeline.py), so clearing first is safe there. Only
    fires when the orchestrator explicitly signals a full regeneration (--full-regen
    CLI flag, or "fullRegen" in the A2A context) — a standalone/custom --task
    invocation (e.g. a narrow manual edit) never sets this, so existing files are
    left untouched by default, matching every "must not wipe" case already audited
    (custom --task edits, frontend-only reruns, qa-agent reading the existing app).
    frontend/ belongs to a separate agent (frontend_agent.py) and is not covered here.
    """
    if _is_cloud_store():
        return
    service_dir = _service_dir(target_app)
    removed = 0
    for name in ("app", "schemas", "tests"):
        path = service_dir / name
        if path.is_dir():
            shutil.rmtree(path)
            removed += 1
    env_path = service_dir / ".env"
    if env_path.is_file():
        env_path.unlink()
        removed += 1
    if removed:
        print(
            f"[developer-agent] --full-regen: cleared {removed} stale app-tree entries",
            file=sys.stderr,
        )


# Deliberately-curated SUBSET of scaffold.py's manifest-derived force-refresh set
# (see `always_refresh` in scaffold.py, ~line 89) — used here to hard-block LLM
# writes rather than just force-copy. Must stay a subset: anything added here must
# also exist in scaffold-manifest.json's copy_verbatim/copy_as for its pattern, and
# must NOT be listed in customize_after_scaffold. Covered by
# tests/test_developer_agent.py::test_verbatim_scaffold_suffixes_is_subset_of_manifest_force_refresh.
_VERBATIM_SCAFFOLD_SUFFIXES = (
    ("app", "database.py"),
    ("app", "startup_checks.py"),
    ("app", "routers", "health.py"),
    ("app", "models", "pg_types.py"),
    ("app", "security.py"),
    ("app", "dependencies.py"),
    ("app", "routers", "auth.py"),
    ("schemas", "auth.py"),
)

# The JWT-only trio within _VERBATIM_SCAFFOLD_SUFFIXES — never scaffolded in
# api-key mode (pattern "B-api-key" has no security.py/routers/auth.py/schemas/auth.py
# in its copy_verbatim). app/dependencies.py is NOT in this set: it's the fixed,
# force-refreshed file in both modes (JWT dependencies.py vs api-key dependencies.py),
# just sourced from a different template file.
_JWT_ONLY_VERBATIM_SUFFIXES = (
    ("app", "security.py"),
    ("app", "routers", "auth.py"),
    ("schemas", "auth.py"),
)


def _verbatim_scaffold_suffixes_for_mode(auth_mode: str) -> tuple[tuple[str, ...], ...]:
    """Mode-aware view of _VERBATIM_SCAFFOLD_SUFFIXES.

    In api-key mode, blocking writes to the JWT trio's paths would be actively
    misleading — those files are never scaffolded, so the block's own error message
    ("call dev_scaffold(..., force=True) to re-copy it unchanged") is a dead end.
    """
    if auth_mode == "api-key":
        return tuple(
            suffix for suffix in _VERBATIM_SCAFFOLD_SUFFIXES
            if suffix not in _JWT_ONLY_VERBATIM_SUFFIXES
        )
    return _VERBATIM_SCAFFOLD_SUFFIXES


def _validate_dev_write_path(file_path: Path) -> str | None:
    """Return an error string if this path must not be written by developer-agent."""
    parts = set(file_path.parts)
    if "_template" in {part.strip().casefold() for part in file_path.parts}:
        return (
            "Error: target-apps/_template is read-only; "
            "call dev_scaffold to copy template files into the target app"
        )
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
    if (
        _current_auth_mode() == "api-key"
        and name == "auth.py"
        and file_path.parent.name == "app"
    ):
        return (
            "Error: app/auth.py is forbidden in api-key mode — there is exactly one "
            "fixed auth header (X-API-Key) and it lives entirely in app/dependencies.py. "
            "Import require_api_key / CurrentUser / require_role from there; do not add "
            "a second auth file or a second header."
        )
    path_parts = file_path.parts
    for suffix in _verbatim_scaffold_suffixes_for_mode(_current_auth_mode()):
        if path_parts[-len(suffix) :] == suffix:
            rel = "/".join(suffix)
            return (
                f"Error: {rel} is a golden template file copied verbatim from _template/ — "
                f"do not hand-write it. Call dev_scaffold(service, pattern, force=True) to "
                "(re)copy it unchanged."
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


def _refresh_developer_handoff_safe() -> None:
    """Persist an in-progress developer-handoff as files land.

    The handoff is normally written once in ``run_task``'s ``finally`` block. When the
    developer-agent runtime is killed at its A2A timeout, that final write is lost even
    though app code already streamed to S3. Refreshing the handoff incrementally means a
    mid-run termination still leaves a usable handoff for gitlab-agent / qa-agent.
    Best-effort: never raise into the calling tool.
    """
    ctx = _run_context
    if ctx is None or not resolve_run_id(ctx):
        return
    written = _dedupe_preserve_order(_written_files)
    if not written:
        return
    app = slugify(str(ctx.get("targetApp") or ctx.get("target_app") or ""))
    if not app:
        return
    try:
        _persist_developer_handoff(app, ctx, written, status="in_progress")
    except Exception:
        logger.debug("[developer-agent] incremental handoff refresh failed", exc_info=True)


@tool
def dev_list_tree(service: str, subpath: str = "") -> str:
    """List files under the service app root (optionally under subpath)."""
    prefix = f"{target_app_root_rel(slugify(service))}/"
    if subpath.strip():
        prefix = f"{prefix}{subpath.strip().strip('/')}/"
    ctx = _run_context
    run_id = resolve_run_id(ctx) if ctx else None
    if run_id and is_s3_store():
        paths = [
            key
            for key in list_run_artifact_keys(run_id)
            if key.startswith(prefix) and not key.endswith("/")
        ]
        return "\n".join(paths) if paths else "(no files)"

    try:
        root = _ensure_service_exists(service)
    except ValueError as exc:
        return f"Error: {exc}"
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


def _current_auth_mode() -> str:
    """Read authMode from the pipeline context passed into this developer-agent run.

    Not surfaced to the LLM — only used internally to resolve which scaffold
    pattern/write-guard applies. Defaults to "jwt" (byte-identical to pre-authMode
    behavior) when authMode is absent, exactly like auth_profile.py's own default.
    """
    ctx = _run_context or {}
    return str(ctx.get("authMode") or "jwt").strip().lower()


def _resolve_scaffold_pattern_for_auth_mode(pattern: str, auth_mode: str) -> str:
    """Swap base pattern "B" for "B-api-key" when authMode is api-key.

    jwt (default) is byte-identical to today: "B" resolves to "B" exactly.
    B+/B++/C (which extend "B") are not branched yet — an api-key app needing
    Bedrock/Streamlit is a follow-up, not handled here.
    """
    if pattern == "B" and auth_mode == "api-key":
        return "B-api-key"
    return pattern


@tool
def dev_scaffold(service: str, pattern: str, force: bool = False) -> str:
    """Copy golden template infrastructure into target-apps/<service>/.

    Call once per app (Step 2c) before writing domain code. Patterns: B, B+, B++, C.
    Manifest: target-apps/_template/scaffold-manifest.json
    Pattern "B" automatically resolves to the api-key file set instead of the JWT
    trio when the run's authMode context is "api-key" — callers still just pass "B".

    Args:
        service: target app slug (e.g. standup-tracker)
        pattern: B | B+ | B++ | C
        force: when True, overwrite existing scaffold files from _template/
    """
    resolved_pattern = _resolve_scaffold_pattern_for_auth_mode(pattern, _current_auth_mode())
    try:
        dest = _ensure_service_exists(service)
        result = scaffold_service(
            template_dir=_TEMPLATE_DIR,
            service_dir=dest,
            pattern=resolved_pattern,
            force=force,
        )
    except (ValueError, FileNotFoundError) as exc:
        return f"SCAFFOLD ERROR: {exc}"

    local_prefix = f"target-apps/{slugify(service)}/"
    for rel in result["copied"]:
        local_full = f"{local_prefix}{rel}"
        if local_full not in _written_files:
            _written_files.append(local_full)
        if _run_context is not None:
            content = (dest / rel).read_bytes()
            write_repo_artifact(_cloud_artifact_rel(local_full), content, context=_run_context)

    if result["copied"]:
        _refresh_developer_handoff_safe()

    return format_scaffold_report(result, service=slugify(service))


@tool
def dev_read_file(path: str) -> str:
    """Read a repo file. Allowed: target-apps/, docs/, agents/, inputs/.
    Use to read PRD, design doc, database handoff, and scraped markdown."""
    raw = path.strip().replace("\\", "/")
    ctx = _run_context
    run_id = resolve_run_id(ctx) if ctx else None
    if run_id:
        cloud_rel = _cloud_artifact_rel(raw)
        for attempt in dict.fromkeys([cloud_rel, raw]):
            try:
                return read_repo_artifact(attempt, context=ctx).decode("utf-8")
            except FileNotFoundError:
                continue
            except UnicodeDecodeError:
                return f"Error: binary or non-utf8 file: {path}"
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
    if _run_context is not None:
        write_repo_artifact(_cloud_artifact_rel(rel), content, context=_run_context)
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
        if _run_context is not None:
            write_repo_artifact(_cloud_artifact_rel(rel), content, context=_run_context)
        written.append(rel)

    if written:
        _refresh_developer_handoff_safe()

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


def _validation_verbose() -> bool:
    return os.getenv("DEVELOPER_AGENT_VERBOSE_VALIDATE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _extract_pytest_summary(stdout: str) -> str:
    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if stripped and any(token in stripped for token in ("passed", "failed", "error", "skipped")):
            return stripped
    return stdout.strip() or "ok"


def _format_validation_success(
    checks: list[str],
    warnings: list[str],
    *,
    pytest_summary: str | None = None,
    health_routes: int = 0,
) -> str:
    lines = [f"All checks passed: {', '.join(checks)}."]
    if pytest_summary:
        lines.append(f"Pytest: {pytest_summary}")
    if health_routes:
        lines.append(f"Health smoke: ok ({health_routes} GET route(s) probed)")
    elif "health" in checks:
        lines.append("Health smoke: ok")
    if warnings:
        lines.append("Notes:")
        lines.extend(f"  - {w}" for w in warnings)
    return "\n".join(lines)


def _format_validation_failure(
    failed_step: str,
    detail: str,
    passed_checks: list[str],
    warnings: list[str],
) -> str:
    lines = [f"Validation failed at {failed_step}:", detail.rstrip()]
    if passed_checks:
        lines.append(f"Passed before failure: {', '.join(passed_checks)}")
    if warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {w}" for w in warnings)
    return "\n".join(lines)


def _python_for_service(service_dir: Path) -> str:
    import platform

    if platform.system() == "Windows":
        venv_python = service_dir / ".venv" / "Scripts" / "python.exe"
        repo_python = _REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = service_dir / ".venv" / "bin" / "python"
        repo_python = _REPO_ROOT / ".venv" / "bin" / "python"
    if venv_python.is_file():
        return str(venv_python)
    if repo_python.is_file():
        return str(repo_python)
    return "python"


def _repo_python_for_shared_tools() -> str:
    """Interpreter for SHARED _shared/*.py tools (e.g. verify_seed_bcrypt.py).

    These depend on repo-level packages (bcrypt, psycopg, etc.) that the
    per-app venv does not install. Always use the repo/main venv, never the
    app venv that _python_for_service() prefers for running the app's own
    tests.
    """
    import platform

    if platform.system() == "Windows":
        repo_python = _REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        repo_python = _REPO_ROOT / ".venv" / "bin" / "python"
    if repo_python.is_file():
        return str(repo_python)
    return "python"


def _ensure_service_requirements_installed(
    service_dir: Path,
    python_cmd: str,
) -> tuple[bool, str]:
    """Install target-app requirements into the interpreter used for validation."""
    import subprocess

    req_files: list[Path] = []
    main_reqs = service_dir / "requirements.txt"
    if main_reqs.is_file():
        req_files.append(main_reqs)
    ui_reqs = service_dir / "ui" / "requirements.txt"
    if ui_reqs.is_file():
        req_files.append(ui_reqs)

    if not req_files:
        return True, ""

    for req_file in req_files:
        rel = req_file.relative_to(service_dir).as_posix()
        try:
            result = subprocess.run(
                [python_cmd, "-m", "pip", "install", "-q", "-r", str(req_file)],
                cwd=str(service_dir),
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return False, f"DEPS FAILED: pip install timed out for {rel}"
        if result.returncode != 0:
            detail = (result.stdout + result.stderr).strip()
            if len(detail) > 2000:
                detail = detail[-2000:]
            return False, f"DEPS FAILED: pip install -r {rel}:\n{detail}"

    return True, ""

def validate_users_auth_columns(service_dir: Path, auth_mode: str = "jwt") -> list[str]:
    """Ensure the users table has the standard auth columns the fixed auth code needs.

    jwt mode: the fixed auth router queries User.username and User.password_hash.
    If the generated users table lacks either, login fails at runtime.

    api-key mode: the fixed require_api_key dependency (app/dependencies.py)
    looks callers up by User.token and reads User.role. This is a hardcoded
    requirement (see auth_profile.py / the api-key design) — every api-key app
    MUST have a users table with token (unique, opaque per-user secret) and
    role columns; there is no "no users table" escape hatch in this mode
    because the fixed dependency has nowhere else to resolve identity from.

    Returns a list of error strings (empty = OK).
    """
    errors: list[str] = []
    sql_dir = service_dir / "db" / "sql"
    if not sql_dir.is_dir():
        if auth_mode == "api-key":
            errors.append(
                "USERS TABLE MISSING: api-key mode requires a users table with "
                "token and role columns (db/sql/ not found)."
            )
        return errors

    users_sql = ""
    for sql_file in sorted(sql_dir.glob("*.sql")):
        text = sql_file.read_text(encoding="utf-8", errors="ignore")
        m = re.search(
            r"create\s+table\s+(if\s+not\s+exists\s+)?[\"\w\.]*users\b.*?\((.*?)\)\s*;",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            users_sql = m.group(2).lower()
            break

    if auth_mode == "api-key":
        if not users_sql:
            errors.append(
                "USERS TABLE MISSING: api-key mode's fixed require_api_key dependency "
                "requires a users table with token and role columns, but no users "
                "CREATE TABLE was found in db/sql/."
            )
            return errors
        if "token" not in users_sql:
            errors.append(
                "USERS TABLE MISSING COLUMN: 'token' not found in the users table. "
                "The fixed require_api_key dependency (app/dependencies.py) looks callers "
                "up by users.token — this is a hardcoded requirement, not optional."
            )
        if "role" not in users_sql:
            errors.append(
                "USERS TABLE MISSING COLUMN: 'role' not found in the users table. "
                "The fixed require_role helper (app/dependencies.py) reads users.role."
            )
        return errors

    if not users_sql:
        if (service_dir / "app" / "routers" / "auth.py").is_file():
            errors.append(
                "USERS TABLE MISSING: the fixed auth router requires a users table with "
                "username and password_hash columns, but no users CREATE TABLE was found in db/sql/."
            )
        return errors

    if "username" not in users_sql:
        errors.append(
            "USERS TABLE MISSING COLUMN: 'username' not found in the users table. "
            "The fixed auth router logs in by username."
        )
    if "password_hash" not in users_sql:
        errors.append(
            "USERS TABLE MISSING COLUMN: 'password_hash' not found in the users table. "
            "The fixed auth router verifies against password_hash."
        )
    return errors


_MAIN_AUTH_IMPORT_RE = re.compile(
    r"^\s*from\s+app\.routers\s+import\s+.*\bauth\b|^\s*import\s+app\.routers\.auth\b",
    re.MULTILINE,
)
_MAIN_AUTH_INCLUDE_RE = re.compile(r"include_router\(\s*auth\.router\b")


def validate_main_registers_auth(service_dir: Path, auth_mode: str = "jwt") -> list[str]:
    """Ensure app/main.py actually imports and registers the fixed auth router.

    routers/auth.py is force-refreshed onto disk (_VERBATIM_SCAFFOLD_SUFFIXES) and
    the template's main.py pre-wires the registration, but neither guarantees the
    LLM's generated main.py keeps the `from app.routers import auth` +
    `include_router(auth.router, ...)` lines — main.py is LLM-written from a seed,
    not force-refreshed. Proven to drift in practice: present on it-asset-lifecycle,
    silently dropped on desk-booking, same prompt instruction both times. This is
    the deterministic backstop. Returns a list of error strings (empty = OK).

    api-key mode has no auth router at all — skip immediately on auth_mode
    rather than relying only on routers/auth.py's absence (kept as a second,
    redundant guard below in case auth_mode is somehow wrong).
    """
    if auth_mode == "api-key":
        return []
    errors: list[str] = []
    if not (service_dir / "app" / "routers" / "auth.py").is_file():
        return errors  # no fixed auth router scaffolded for this app/pattern

    main_path = service_dir / "app" / "main.py"
    if not main_path.is_file():
        errors.append("MAIN.PY MISSING: app/main.py not found — cannot register the fixed auth router.")
        return errors

    text = main_path.read_text(encoding="utf-8", errors="ignore")
    if not _MAIN_AUTH_IMPORT_RE.search(text):
        errors.append(
            "AUTH ROUTER NOT IMPORTED: app/main.py does not import auth from app.routers — "
            "login will 404. Add `from app.routers import auth` "
            "(see target-apps/_template/app/main.py)."
        )
    if not _MAIN_AUTH_INCLUDE_RE.search(text):
        errors.append(
            "AUTH ROUTER NOT REGISTERED: app/main.py does not call "
            'app.include_router(auth.router, tags=["auth"]) — login will 404. '
            "Register it with NO prefix, right next to the health router "
            "(see target-apps/_template/app/main.py)."
        )
    return errors


_ME_IMPORT_RE = re.compile(
    r"^\s*from\s+app\.routers\s+import\s+.*\bme\b|^\s*import\s+app\.routers\.me\b",
    re.MULTILINE,
)
_ME_INCLUDE_RE = re.compile(r"include_router\(\s*me\.router\b")

# Matches the single combined `from app.routers import a, b, c` line every
# scaffolded main.py uses (see _JWT_MAIN_PY_SECTION / _API_KEY_MAIN_PY_SECTION
# examples above) — captures the name list so `me` can be appended to it.
_ROUTERS_IMPORT_LINE_RE = re.compile(
    r"^(?P<indent>[ \t]*)from\s+app\.routers\s+import\s+(?P<names>[^\n#]+?)[ \t]*(?P<comment>#.*)?$",
    re.MULTILINE,
)
# Anchor for where to inject the me.router registration, and for which FastAPI
# app variable name (`app` vs `application`, etc.) this file actually uses —
# health is always present (force-refreshed by the scaffolder), so it's a safe,
# always-present anchor line.
_HEALTH_INCLUDE_LINE_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<var>\w+)\.include_router\(\s*health\.router\b[^\n]*\)[ \t]*$",
    re.MULTILINE,
)


def autofix_main_registers_me(service_dir: Path, auth_mode: str) -> list[str]:
    """Deterministically register app/routers/me.py's GET /api/v1/users/me route in
    app/main.py for api-key apps.

    me.py is never scaffolded for JWT apps and this is a no-op there. For
    api-key apps it's now force-refreshed onto disk (scaffold-manifest.json's
    B-api-key copy_verbatim), but app/main.py is LLM-written per app, not
    template-copied (see validate_main_registers_auth's docstring — same drift
    risk observed for the auth router), and the frontend's verbatim api.ts
    hardcodes a login call to this exact route regardless of what the model
    wrote. me.py declares the FULL path (@router.get("/api/v1/users/me")), so
    it must be registered with NO prefix — adding one would double the path to
    /api/v1/users/api/v1/users/me.

    Only rewrites main.py when its shape is unambiguous (exactly one combined
    `from app.routers import ...` line and exactly one health include_router
    call to anchor on and to read the app variable name from). Returns a
    one-item list describing the injection when applied (for a non-blocking
    _warn), or [] when there's nothing to do — JWT mode, me.py not scaffolded,
    already registered (idempotent), or the shape isn't safe to touch. In the
    last case the file is left untouched and validate_main_registers_me (the
    paired blocking check) reports it instead of risking a corrupt inject.
    """
    if auth_mode != "api-key":
        return []
    me_path = service_dir / "app" / "routers" / "me.py"
    if not me_path.is_file():
        return []
    main_path = service_dir / "app" / "main.py"
    if not main_path.is_file():
        return []
    text = main_path.read_text(encoding="utf-8", errors="ignore")
    if _ME_IMPORT_RE.search(text) and _ME_INCLUDE_RE.search(text):
        return []

    import_matches = list(_ROUTERS_IMPORT_LINE_RE.finditer(text))
    health_matches = list(_HEALTH_INCLUDE_LINE_RE.finditer(text))
    if len(import_matches) != 1 or len(health_matches) != 1:
        return []

    im = import_matches[0]
    names = im.group("names").rstrip()
    if not re.search(r"\bme\b", names):
        new_import_line = f"{im.group('indent')}from app.routers import {names}, me"
        if im.group("comment"):
            new_import_line += f"  {im.group('comment')}"
        text = text[: im.start()] + new_import_line + text[im.end() :]
        # Re-anchor: the import edit shifted every later offset, including the
        # health include line further down the file.
        health_matches = list(_HEALTH_INCLUDE_LINE_RE.finditer(text))
        if len(health_matches) != 1:
            return []

    if not _ME_INCLUDE_RE.search(text):
        hm = health_matches[0]
        injected_line = f'\n{hm.group("indent")}{hm.group("var")}.include_router(me.router, tags=["users"])'
        text = text[: hm.end()] + injected_line + text[hm.end() :]

    main_path.write_text(text, encoding="utf-8")
    return [
        "app/main.py did not register app/routers/me.py's GET /api/v1/users/me "
        "(the frontend's login flow calls it) — injected `me` into the routers "
        'import and added include_router(me.router, tags=["users"]) with no prefix'
    ]


def validate_main_registers_me(service_dir: Path, auth_mode: str = "jwt") -> list[str]:
    """Ensure app/main.py registers app/routers/me.py's GET /api/v1/users/me route.

    Paired with autofix_main_registers_me, which runs first and injects the
    registration when main.py's shape is safe to edit. This is the
    deterministic backstop for the case autofix declined to touch (unexpected
    main.py shape) — same "prefer safe-block over corrupt-inject" policy as the
    ui_parity stray-file auto-remove. api-key apps only: JWT apps have no
    me.py and their api.ts never calls /users/me.
    """
    if auth_mode != "api-key":
        return []
    me_path = service_dir / "app" / "routers" / "me.py"
    if not me_path.is_file():
        return []
    main_path = service_dir / "app" / "main.py"
    if not main_path.is_file():
        return ["MAIN.PY MISSING: app/main.py not found — cannot register app/routers/me.py."]
    text = main_path.read_text(encoding="utf-8", errors="ignore")
    errors: list[str] = []
    if not _ME_IMPORT_RE.search(text):
        errors.append(
            "ME ROUTER NOT IMPORTED: app/main.py does not import me from app.routers — "
            "the frontend's login flow calls GET /api/v1/users/me and will 404. Add "
            "`me` to the `from app.routers import ...` line "
            "(see target-apps/_template/app/routers/me.py)."
        )
    if not _ME_INCLUDE_RE.search(text):
        errors.append(
            "ME ROUTER NOT REGISTERED: app/main.py does not call "
            "include_router(me.router, ...) — GET /api/v1/users/me will 404. "
            "Register it with NO prefix — me.py's route is already the full path "
            "/api/v1/users/me, so adding a prefix would double it."
        )
    return errors


_CORS_IMPORT_RE = re.compile(r"from\s+fastapi\.middleware\.cors\s+import\s+CORSMiddleware")
_CORS_ADD_MIDDLEWARE_RE = re.compile(r"add_middleware\s*\(\s*CORSMiddleware\b")
_CORS_ORIGINS_FIELD_RE = re.compile(r"\bcors_origins\s*:")


def validate_cors_configured(service_dir: Path) -> list[str]:
    """Ensure app/main.py registers CORSMiddleware and app/config.py exposes
    cors_origins for it to read.

    Both target-apps/_template/app/main.py and main_apikey.py wire this
    correctly, but neither app/main.py nor app/config.py is force-refreshed
    (they're not in _VERBATIM_SCAFFOLD_SUFFIXES — the LLM hand-writes both per
    app), so the wiring can silently drop the same way validate_main_registers_
    auth's docstring describes for the auth router. Every generated app ships
    a browser frontend that sends a custom header (Authorization or
    X-API-Key), so the browser always preflights with an OPTIONS request first.
    Starlette's router 405s an OPTIONS request for a path with no OPTIONS
    handler unless CORSMiddleware is registered — with no login/API call ever
    reaching the backend, the frontend just shows "Failed to load" and the
    only signal is 405s on every OPTIONS line in the server log. Returns a
    list of error strings (empty = OK).
    """
    errors: list[str] = []
    main_path = service_dir / "app" / "main.py"
    if not main_path.is_file():
        return ["MAIN.PY MISSING: cannot check CORS configuration."]
    main_text = main_path.read_text(encoding="utf-8", errors="ignore")

    if not _CORS_IMPORT_RE.search(main_text):
        errors.append(
            "CORS MIDDLEWARE MISSING: app/main.py does not import CORSMiddleware "
            "from fastapi.middleware.cors. Without it every browser preflight "
            "OPTIONS request gets FastAPI's default 405 and no real request from "
            "the frontend ever reaches the API. Add `from fastapi.middleware.cors "
            "import CORSMiddleware` and `app.add_middleware(CORSMiddleware, "
            "allow_origins=settings.cors_origins, allow_credentials=True, "
            'allow_methods=["*"], allow_headers=["*"])` right after the FastAPI() '
            "call (see target-apps/_template/app/main.py or main_apikey.py)."
        )
    elif not _CORS_ADD_MIDDLEWARE_RE.search(main_text):
        errors.append(
            "CORS MIDDLEWARE NOT REGISTERED: CORSMiddleware is imported in "
            "app/main.py but never passed to add_middleware(...) — preflight "
            "OPTIONS requests will still 405. Add "
            "`app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, "
            'allow_credentials=True, allow_methods=["*"], allow_headers=["*"])`.'
        )

    config_path = service_dir / "app" / "config.py"
    config_text = config_path.read_text(encoding="utf-8", errors="ignore") if config_path.is_file() else ""
    if not _CORS_ORIGINS_FIELD_RE.search(config_text):
        errors.append(
            "CORS_ORIGINS MISSING: app/config.py has no cors_origins setting — "
            "app/main.py's CORSMiddleware(allow_origins=settings.cors_origins) has "
            'nothing to read. Add `cors_origins: list[str] = Field(default_factory='
            'lambda: ["*"], alias="CORS_ORIGINS")` to the Settings class.'
        )
    return errors


_REQUIRE_API_KEY_DEF_RE = re.compile(r"\bdef\s+require_api_key\s*\(")
_GET_CURRENT_USER_DEF_RE = re.compile(r"\bdef\s+get_current_user\s*\(")

# Only ever scaffolded in jwt mode (pattern "B") — never present in "B-api-key".
_JWT_ONLY_TRIO_RELPATHS: tuple[tuple[str, ...], ...] = (
    ("app", "security.py"),
    ("app", "routers", "auth.py"),
    ("schemas", "auth.py"),
)


def validate_auth_mode_files(service_dir: Path, auth_mode: str) -> list[str]:
    """Cross-check authMode against what's actually on disk in app/dependencies.py,
    the JWT-only trio, and app/main.py — catches auth files leaking across modes
    (e.g. a full-regen that didn't clear stale files, or dev_scaffold called with
    the wrong pattern for the declared authMode).

    api-key mode:
      - app/dependencies.py must be the api-key variant (require_api_key present).
      - none of the JWT-only trio (security.py, routers/auth.py, schemas/auth.py)
        may exist — those are only ever scaffolded in jwt mode.
      - app/main.py must not import or register an auth router — there is no
        login route in this mode.

    jwt mode:
      - app/dependencies.py must not be the api-key variant (require_api_key
        present with no get_current_user) — the reverse leak.

    Returns a list of error strings (empty = OK).
    """
    errors: list[str] = []
    deps_path = service_dir / "app" / "dependencies.py"
    deps_text = deps_path.read_text(encoding="utf-8", errors="ignore") if deps_path.is_file() else ""
    has_require_api_key = bool(_REQUIRE_API_KEY_DEF_RE.search(deps_text))
    has_get_current_user = bool(_GET_CURRENT_USER_DEF_RE.search(deps_text))

    if auth_mode == "api-key":
        if not deps_path.is_file():
            errors.append(
                "DEPENDENCIES.PY MISSING: api-key mode requires app/dependencies.py with "
                'require_api_key. Call dev_scaffold(service, pattern="B", force=True) to '
                "copy it."
            )
        elif not has_require_api_key:
            errors.append(
                "DEPENDENCIES.PY WRONG VARIANT: authMode is api-key but app/dependencies.py "
                "has no require_api_key function — this looks like the JWT variant leaked in "
                '(no login flow exists in api-key mode). Call dev_scaffold(service, pattern="B", '
                "force=True) to re-copy the api-key variant."
            )
        for suffix in _JWT_ONLY_TRIO_RELPATHS:
            leaked_path = service_dir / Path(*suffix)
            if leaked_path.is_file():
                rel = "/".join(suffix)
                # api-key mode deterministically never has these files, so an
                # LLM-generated leak is auto-removed rather than failing the
                # whole build — there is nothing to "fix" other than deleting it.
                leaked_path.unlink()
                print(
                    f"[developer-agent] AUTH_MODE_FILES: auto-removed {rel} "
                    "(JWT-only file leaked into api-key mode app)",
                    file=sys.stderr,
                )
        main_path = service_dir / "app" / "main.py"
        if main_path.is_file():
            main_text = main_path.read_text(encoding="utf-8", errors="ignore")
            if _MAIN_AUTH_IMPORT_RE.search(main_text) or _MAIN_AUTH_INCLUDE_RE.search(main_text):
                errors.append(
                    "AUTH ROUTER IN API-KEY APP: app/main.py imports or registers an auth "
                    "router, but authMode is api-key — there is no login route in this mode. "
                    "Remove `from app.routers import auth` and "
                    "`app.include_router(auth.router, ...)` (see "
                    "target-apps/_template/app/main_apikey.py)."
                )
    else:
        if deps_path.is_file() and has_require_api_key and not has_get_current_user:
            errors.append(
                "DEPENDENCIES.PY WRONG VARIANT: authMode is jwt but app/dependencies.py has "
                "require_api_key and no get_current_user — this looks like the api-key variant "
                'leaked in. Call dev_scaffold(service, pattern="B", force=True) to re-copy the '
                "JWT variant."
            )
    return errors


_API_KEY_DEPENDS_RE = re.compile(
    r"Depends\(\s*require_api_key\s*\)|dependencies\s*=\s*\[[^\]]*\brequire_api_key\b"
)
_REQUIRE_ROLE_DEPENDS_RE = re.compile(
    r"Depends\(\s*require_role\(|dependencies\s*=\s*\[[^\]]*\brequire_role\("
)


def validate_api_key_route_usage(service_dir: Path) -> list[str]:
    """api-key mode only: at least one route must actually apply the fixed
    require_api_key / require_role(...) dependency.

    Catches the case where app/dependencies.py has the right shape
    (validate_auth_mode_files passes) but no route ever wires it in — auth is
    defined but never applied, so every endpoint is effectively public. Only
    two names ever count, matching the hardcoded single-header design: there
    is no per-app auth-enforcing function to discover anymore.

    Returns a list of error strings (empty = OK).
    """
    routers_dir = service_dir / "app" / "routers"
    if not routers_dir.is_dir():
        return ["NO ROUTERS: app/routers/ not found — cannot check require_api_key usage."]
    for path in routers_dir.glob("*.py"):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if _API_KEY_DEPENDS_RE.search(text) or _REQUIRE_ROLE_DEPENDS_RE.search(text):
            return []
    return [
        "REQUIRE_API_KEY NEVER APPLIED: authMode is api-key but no route in "
        "app/routers/*.py applies Depends(require_api_key) or "
        "Depends(require_role(...)) — every endpoint is effectively public. "
        "Apply one on at least the routes design Rules require auth on."
    ]


# Any APIKeyHeader(...) declaration, or a bare Header(...) call whose alias
# looks like an auth/identity header (X-...) — both are ways a second,
# invented auth header could sneak in outside the one fixed scheme in
# app/dependencies.py. Restricting the alias capture to "X-..." avoids
# matching unrelated kwargs like scheme_name=.
_APIKEYHEADER_DECL_RE = re.compile(r"\bAPIKeyHeader\s*\(")
_HEADER_CALL_RE = re.compile(r"\bHeader\s*\(")
_HEADER_ALIAS_RE = re.compile(r'(?:alias|name)\s*=\s*["\'](X-[^"\']+)["\']')


def _scan_invented_auth_headers(service_dir: Path) -> list[str]:
    """Find any auth-header declaration in generated app code OUTSIDE the fixed
    app/dependencies.py — the only file allowed to read X-API-Key. Catches an
    invented second APIKeyHeader scheme (e.g. X-Admin-Key) and a bare
    Header(alias="X-User-Id")-style parameter alike; both are forbidden by the
    hardcoded single-header design regardless of what the design doc's prose
    suggests.
    """
    findings: list[str] = []
    app_dir = service_dir / "app"
    if not app_dir.is_dir():
        return findings
    fixed_deps_path = (app_dir / "dependencies.py").resolve()
    for path in app_dir.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if path.resolve() == fixed_deps_path:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.relative_to(service_dir).as_posix()
        if _APIKEYHEADER_DECL_RE.search(text):
            findings.append(f"{rel}: declares a second APIKeyHeader(...) scheme")
        for m in _HEADER_CALL_RE.finditer(text):
            window = text[m.start() : m.start() + 200]
            alias_m = _HEADER_ALIAS_RE.search(window)
            if alias_m:
                findings.append(
                    f'{rel}: bare Header(alias="{alias_m.group(1)}") auth parameter'
                )
    return findings


_FRONTEND_HEADER_ENV_RE = re.compile(r"^\s*VITE_API_KEY_HEADER\s*=\s*(\S+)\s*$", re.MULTILINE)


def _frontend_configured_header(service_dir: Path) -> str | None:
    """Header name the frontend will actually send, read from frontend/.env
    (falling back to frontend/.env.example). Returns the api_apikey.ts template's
    own runtime default ("X-API-Key") when a frontend exists but neither file
    sets VITE_API_KEY_HEADER, and None when there's no frontend at all (nothing
    to cross-check).
    """
    for rel in ("frontend/.env", "frontend/.env.example"):
        path = service_dir / rel
        if not path.is_file():
            continue
        m = _FRONTEND_HEADER_ENV_RE.search(path.read_text(encoding="utf-8", errors="ignore"))
        if m:
            return m.group(1).strip().strip('"').strip("'")
    if (service_dir / "frontend").is_dir():
        return "X-API-Key"
    return None


def validate_no_invented_auth_headers(service_dir: Path, auth_mode: str) -> list[str]:
    """api-key mode only: hard-fail if anything besides the fixed
    app/dependencies.py reads an auth header, or if app/auth.py exists at all.

    This is the deterministic backstop for the hardcoded single-header design
    (ONE auth header, ever: X-API-Key; no X-User-Id, no X-Admin-Key, no second
    header of any kind) — the write-guard in _validate_dev_write_path already
    blocks writing app/auth.py, and app/dependencies.py's shape is fixed, but
    neither stops a route file from declaring its own Header(...)/
    APIKeyHeader(...) parameter inline. This is exactly the bug class that
    broke a prior run (a bare X-User-Id Header() the LLM added despite the
    design instructing otherwise).

    Returns a list of error strings (empty = OK).
    """
    if auth_mode != "api-key":
        return []
    errors: list[str] = []
    if (service_dir / "app" / "auth.py").is_file():
        errors.append(
            "APP/AUTH.PY FORBIDDEN: api-key mode has exactly one fixed auth file, "
            "app/dependencies.py. Delete app/auth.py and move any route wiring to "
            "use require_api_key / CurrentUser / require_role from there."
        )
    for finding in _scan_invented_auth_headers(service_dir):
        errors.append(
            f"INVENTED AUTH HEADER: {finding} — the only allowed auth header is "
            "X-API-Key via app/dependencies.py's require_api_key. Remove it and "
            "use require_api_key / require_role instead."
        )
    frontend_header = _frontend_configured_header(service_dir)
    if frontend_header and frontend_header.strip().lower() != "x-api-key":
        errors.append(
            "FRONTEND HEADER MISMATCH: frontend is configured (VITE_API_KEY_HEADER) "
            f"to send {frontend_header}, but api-key mode has exactly one header, "
            "X-API-Key. Set VITE_API_KEY_HEADER=X-API-Key (or remove the override)."
        )
    return errors


# Broad type categories shared by both the applied-DB side and the ORM side of
# validate_schema_parity. Only cross-category drift is a real bug (e.g. DB array
# vs ORM string); same-category spelling differences (VARCHAR vs String,
# TIMESTAMP vs TIMESTAMPTZ) are intentionally not distinguished.
_DB_COLUMN_CATEGORY_MAP: dict[str, str] = {
    "uuid": "string",  # folded into string — a DB uuid vs an ORM String must not fail
    "character varying": "string",
    "character": "string",
    "text": "string",
    "citext": "string",
    "USER-DEFINED": "enum",  # native Postgres ENUM types (pg_enum in the ORM)
    "integer": "integer",
    "bigint": "integer",
    "smallint": "integer",
    "numeric": "numeric",
    "double precision": "numeric",
    "real": "numeric",
    "money": "numeric",
    "boolean": "boolean",
    "timestamp without time zone": "timestamp",
    "timestamp with time zone": "timestamp",
    "date": "timestamp",
    "time without time zone": "timestamp",
    "time with time zone": "timestamp",
    "json": "json",
    "jsonb": "json",
}

# Ordered ORM type-expression keyword -> category. Order only matters where a
# keyword is a substring of another (e.g. "Time" in "TimestampTZ"); those cases
# all resolve to the same category so the ambiguity is harmless.
_ORM_TYPE_CATEGORY_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("pg_uuid_column", "string"),  # folded into string — see _DB_COLUMN_CATEGORY_MAP note
    ("PG_UUID", "string"),
    ("UUID", "string"),
    ("pg_enum", "enum"),
    ("SAEnum", "enum"),
    ("Enum", "enum"),
    ("String", "string"),
    ("Unicode", "string"),
    ("Text", "string"),
    ("VARCHAR", "string"),
    ("CHAR", "string"),
    ("BigInteger", "integer"),
    ("SmallInteger", "integer"),
    ("Integer", "integer"),
    ("Numeric", "numeric"),
    ("Float", "numeric"),
    ("Decimal", "numeric"),
    ("Boolean", "boolean"),
    ("TimestampTZ", "timestamp"),
    ("DateTime", "timestamp"),
    ("Date", "timestamp"),
    ("Time", "timestamp"),
    ("JSONB", "json"),
    ("JSON", "json"),
    ("ARRAY", "array"),
)

_MODEL_TABLENAME_RE = re.compile(r'__tablename__\s*=\s*["\']([^"\']+)["\']')
_MODEL_COLUMN_RE = re.compile(
    r'^[ \t]+(\w+)\s*:\s*Mapped\[([^\]]*)\]\s*=\s*mapped_column\(',
    re.MULTILINE,
)
# No-annotation styles: legacy `col = Column(Type, ...)` and bare
# `col = mapped_column(Type, ...)` (mapped_column with no `Mapped[...]` type hint —
# expense-tracker uses this heavily, e.g. `original_amount = mapped_column(Numeric(19,4), ...)`).
# Both lack a Python annotation, so both fall back to the same nullable default.
# Cannot false-match the Mapped[...] style above — that form has a ":" between
# the name and "=", which breaks this pattern before it reaches "= Column("/"= mapped_column(".
_MODEL_COLUMN_LEGACY_RE = re.compile(
    r'^[ \t]+(\w+)\s*=\s*(?:Column|mapped_column)\(',
    re.MULTILINE,
)


def _db_column_category(data_type: str, udt_name: str) -> str:
    if data_type == "ARRAY" or udt_name.startswith("_"):
        return "array"
    return _DB_COLUMN_CATEGORY_MAP.get(data_type, "other")


def _orm_column_category(type_expr: str) -> str:
    for keyword, category in _ORM_TYPE_CATEGORY_KEYWORDS:
        if keyword in type_expr:
            return category
    return "other"


def _find_matching_paren_py(text: str, open_index: int) -> int:
    """Return the index of the ')' matching the '(' at open_index, or -1."""
    depth = 0
    i = open_index
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _split_top_level_commas(text: str) -> list[str]:
    """Split on commas not nested inside (), [], or {} — mirrors validate_sql_artifacts'
    CSV splitting, simplified for Python call-argument text."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def _call_arg_tokens(text: str, open_paren_index: int) -> list[str] | None:
    """Top-level comma-split argument tokens for the call whose '(' is at open_paren_index."""
    close_idx = _find_matching_paren_py(text, open_paren_index)
    if close_idx == -1:
        return None
    return _split_top_level_commas(text[open_paren_index + 1 : close_idx])


def _scan_nullable_pk(kwargs_tokens: list[str]) -> tuple[bool | None, bool, bool]:
    """(explicit nullable=... value if present else None, primary_key=True present,
    server_default=/default= present — a default supplies the value, so the DB
    column is legitimately NOT NULL even when the Python annotation is Optional)."""
    nullable: bool | None = None
    primary_key = False
    has_default = False
    for tok in kwargs_tokens:
        low = tok.lower().replace(" ", "")
        if low.startswith("nullable="):
            nullable = "true" in low.split("=", 1)[1]
        elif low.startswith("primary_key=") and "true" in low:
            primary_key = True
        elif low.startswith("server_default=") or low.startswith("default="):
            has_default = True
    return nullable, primary_key, has_default


def _parse_orm_models(models_dir: Path) -> dict[str, dict[str, tuple[str, bool]]]:
    """Static parse of app/models/*.py — no import. {table: {column: (category, nullable)}}.

    Handles three column styles: SQLAlchemy 2.0 annotated (`col: Mapped[T] = mapped_column(...)`),
    legacy (`col = Column(...)`), and bare mapped_column with no annotation
    (`col = mapped_column(...)`) — an app tends to use one style consistently, but all
    regexes always run and results are merged so a mixed file would still parse. A table
    whose file parses to zero columns is dropped (not compared), so a parse miss produces
    one WARN instead of a wall of false "missing column" errors.
    """
    orm_map: dict[str, dict[str, tuple[str, bool]]] = {}
    if not models_dir.is_dir():
        return orm_map

    for path in sorted(models_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        table_match = _MODEL_TABLENAME_RE.search(text)
        if not table_match:
            continue
        table_name = table_match.group(1)

        columns: dict[str, tuple[str, bool]] = {}

        for col_match in _MODEL_COLUMN_RE.finditer(text):
            col_name = col_match.group(1)
            annotation = col_match.group(2)
            tokens = _call_arg_tokens(text, col_match.end() - 1)
            if not tokens:
                continue
            type_expr, kwargs_tokens = tokens[0], tokens[1:]

            nullable, primary_key, has_default = _scan_nullable_pk(kwargs_tokens)
            if nullable is None:
                if primary_key or has_default:
                    nullable = False
                else:
                    low_annotation = annotation.lower()
                    nullable = "none" in low_annotation or "optional[" in low_annotation

            columns[col_name] = (_orm_column_category(type_expr), nullable)

        for col_match in _MODEL_COLUMN_LEGACY_RE.finditer(text):
            col_name = col_match.group(1)
            if col_name in columns:
                continue  # already captured via the Mapped[...] regex above
            tokens = _call_arg_tokens(text, col_match.end() - 1)
            if not tokens:
                continue
            type_expr, kwargs_tokens = tokens[0], tokens[1:]

            nullable, primary_key, has_default = _scan_nullable_pk(kwargs_tokens)
            if nullable is None:
                # No Mapped[...] annotation to infer from (Column(...) or bare
                # mapped_column(...)) — SQLAlchemy's own default is nullable=True,
                # unless a default supplies the value (server_default=/default=)
                # or it's a primary key.
                nullable = False if (primary_key or has_default) else True

            columns[col_name] = (_orm_column_category(type_expr), nullable)

        if not columns:
            print(
                f"[schema_parity] WARN: could not parse columns for table '{table_name}' "
                f"in {path.name}, skipping parity check for this table"
            )
            continue

        orm_map[table_name] = columns

    return orm_map


def validate_schema_parity(service_dir: Path) -> tuple[list[str], list[str]]:
    """Compare the applied Postgres schema against the static ORM models.

    DB side: introspects information_schema.columns for the app's applied schema
    (same connection approach as _shared/derive_enums.py). ORM side: static text
    parse of app/models/*.py — models are never imported, so this can't crash on
    app-specific import errors. Returns (errors, warnings): a non-empty `errors` list
    fails the developer step the same way validate_rds_parity and
    validate_users_auth_columns do; `warnings` are surfaced in the report but never
    block (PART 4a fix — an unmodeled table used to be a silent print(), now it's a
    reported, non-blocking warning; see the `db_tables - orm_tables` loop below).
    """
    errors: list[str] = []
    warnings: list[str] = []
    app = service_dir.name

    try:
        import psycopg

        from _shared.rds_env import connection_url, load_target_app_env, schema_for_app

        load_target_app_env(app)
        app_schema = schema_for_app(app)
        url = connection_url().replace("postgresql+psycopg://", "postgresql://")

        db_map: dict[str, dict[str, tuple[str, bool]]] = {}
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name, column_name, data_type, udt_name, is_nullable
                FROM information_schema.columns
                WHERE table_schema = %s
                ORDER BY table_name, column_name
                """,
                (app_schema,),
            )
            for table_name, column_name, data_type, udt_name, is_nullable in cur.fetchall():
                category = _db_column_category(data_type, udt_name)
                nullable = is_nullable == "YES"
                db_map.setdefault(table_name, {})[column_name] = (category, nullable)
    except psycopg.OperationalError as exc:
        return [
            f"schema_parity: could NOT CONNECT to the applied Postgres schema ({exc!r}) — "
            f"this usually means the AWS SSO session expired or RDS is unreachable, NOT a code "
            f"bug. Run `aws sso login --profile aryan-sdlc` and retry. The check is blocking "
            f"because it cannot verify ORM/DB parity without a live connection."
        ], []
    except Exception as exc:
        return [
            f"schema_parity: failed to introspect the applied DB schema ({exc!r}) — the DB may "
            f"not have been applied, or the schema is malformed. This check must run against the "
            f"real Postgres schema and cannot be skipped."
        ], []

    orm_map = _parse_orm_models(service_dir / "app" / "models")

    db_tables = set(db_map)
    orm_tables = set(orm_map)

    for table in sorted(orm_tables - db_tables):
        errors.append(
            f"schema_parity: ORM model defines table '{table}' but it does not exist in "
            f"applied DB schema '{app_schema}' — check db/sql/ was applied, or table name typo"
        )

    for table in sorted(db_tables - orm_tables):
        # PART 4a fix: a DB table with no ORM model may be intentional (e.g. an
        # association/join table with no Python-side model) — still NOT a blocking
        # error, so this never triggers _fail — but it must be visible, not a silent
        # print() that only appears with -v. It's collected as a warning and surfaced
        # in every validation report (see run_service_validation's `_warn` wiring).
        warnings.append(
            f"schema_parity: DB table '{table}' (schema '{app_schema}') has no matching "
            "ORM model — comparison skipped for this table. If intentional (e.g. an "
            "association/join table with no Python-side model), no action needed; "
            "otherwise add app/models/<entity>.py for it."
        )

    for table in sorted(db_tables & orm_tables):
        db_cols = db_map[table]
        orm_cols = orm_map[table]
        db_col_names = set(db_cols)
        orm_col_names = set(orm_cols)

        for col in sorted(db_col_names - orm_col_names):
            errors.append(
                f"schema_parity: {table}.{col} exists in applied DB schema '{app_schema}' "
                "but has no matching column in the ORM model"
            )
        for col in sorted(orm_col_names - db_col_names):
            errors.append(
                f"schema_parity: {table}.{col} is defined in the ORM model but does not exist "
                f"in applied DB schema '{app_schema}' — check db/sql/ was applied, or column name typo"
            )
        for col in sorted(db_col_names & orm_col_names):
            db_category, db_nullable = db_cols[col]
            orm_category, orm_nullable = orm_cols[col]
            if db_category != orm_category:
                errors.append(
                    f"schema_parity: {table}.{col} type category mismatch — DB is "
                    f"'{db_category}' but ORM maps to '{orm_category}'"
                )
            if db_nullable != orm_nullable:
                errors.append(
                    f"schema_parity: {table}.{col} nullability mismatch — DB "
                    f"{'allows NULL' if db_nullable else 'is NOT NULL'} but ORM "
                    f"{'allows NULL' if orm_nullable else 'is NOT NULL'}"
                )

    return errors, warnings


def _validation_env(
    service_dir: Path,
    *,
    database_url: str = "",
    postgres_schema: str | None = None,
) -> dict[str, str]:
    """Test env: real Postgres against a throwaway schema when db/sql/ exists (see
    _shared.pg_test_schema.setup_temp_pg_test_schema — this is what makes ORM/DDL
    drift like enum-vs-String visible to pytest); schema/keys from .env.example
    when present.

    database_url/postgres_schema come from setup_temp_pg_test_schema's return value.
    When empty (no db/sql/ — DB-less or non-Postgres app pattern), fall back to the
    harmless in-memory SQLite default these apps never actually read from DATABASE_URL.
    """
    env = {**os.environ}
    example_vars = _parse_dotenv_file(service_dir / ".env.example")
    env.update(example_vars)
    env["APP_ENV"] = "test"
    env["SKIP_STARTUP_CHECKS"] = "1"
    if database_url:
        env["DATABASE_URL"] = database_url
        if postgres_schema:
            env["POSTGRES_SCHEMA"] = postgres_schema
    else:
        env["DATABASE_URL"] = "sqlite:///:memory:"
    if not env.get("API_KEY"):
        env["API_KEY"] = "test-key"
    env.setdefault("JWT_SECRET_KEY", example_vars.get("JWT_SECRET_KEY") or "test-secret-not-for-prod")
    env.setdefault("JWT_ALGORITHM", "HS256")
    env.setdefault("JWT_EXPIRE_MINUTES", "60")
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


def _scan_python_syntax(service_dir: Path) -> list[str]:
    """Compile every generated .py file — catches SyntaxError in files the
    app.main import graph doesn't reach (services only imported by routers
    other than the one under test, tests/conftest.py, etc.)."""
    import py_compile

    errors: list[str] = []
    for path in service_dir.rglob("*.py"):
        if any(part in _BLOCKED_PATH_PARTS for part in path.parts):
            continue
        rel = path.relative_to(service_dir).as_posix()
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"{rel}: {exc.msg}")
    return errors


def _check_py_encodable(service_dir: Path) -> None:
    """Reuse gitlab-agent's publish-time surrogate/syntax check (
    _shared.gitlab_mcp_actions.assert_publish_python_syntax) at generation time,
    so a .py file with unencodable content — e.g. a lone UTF-16 surrogate emoji
    escape like page_icon="\\ud83c\\udfab" — fails the developer step here instead
    of only surfacing at GitLab publish. py_compile accepts these as valid syntax
    (they're legal Python string escapes), but the resulting str can never be
    UTF-8 encoded; Streamlit hits exactly this in st.set_page_config(page_icon=...).

    Imported lazily (not at module top) to match every other validation helper in
    this file (validate_conftest, validate_rds_parity, validate_ui_parity, ...) —
    none of them are top-level imports either, and this keeps the gitlab_mcp_client
    -> mcp package dependency out of developer_agent.py's import graph for runs
    that never exercise this specific check.

    Raises ValueError on any bad or unreadable file — the same exception
    assert_publish_python_syntax itself raises, so callers only need one except
    clause."""
    from _shared.gitlab_mcp_actions import assert_publish_python_syntax

    files: list[dict[str, str]] = []
    for path in service_dir.rglob("*.py"):
        if any(part in _BLOCKED_PATH_PARTS for part in path.parts):
            continue
        rel = path.relative_to(service_dir).as_posix()
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ValueError(f"{rel}: could not read as UTF-8 text ({exc})") from exc
        files.append({"path": rel, "content": content})

    assert_publish_python_syntax(files)


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


_ROUTE_DECORATOR_RE = re.compile(
    r'@router\.(get|post|put|patch|delete)\(\s*["\']([^"\']*)["\']'
)
_DEF_RE = re.compile(r"\bdef\s+\w+\s*\(")
_BODY_PARAM_TYPE_RE = re.compile(r"(?:^|,)\s*body\s*:\s*([A-Za-z_][A-Za-z0-9_]*)")


def _matching_close_paren(text: str, open_paren_idx: int) -> int:
    """Return the index of the ')' matching the '(' at open_paren_idx (paren-depth scan)."""
    depth = 0
    for i in range(open_paren_idx, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _scan_duplicate_action_routes(service_dir: Path) -> list[str]:
    """Flag a bare `{id}` PATCH/PUT route that clones a dedicated `{id}/<action>` route.

    A workflow transition (status/assign/archive/return/...) should exist as exactly
    ONE route: the dedicated sub-path action. When a bare `PATCH/PUT /{id}` route on
    the same resource takes the *same request body schema* as a sibling `{id}/<action>`
    route in the same router file, it is not a real general-update endpoint — it is a
    redundant clone that lets callers bypass the dedicated route while doing the exact
    same state transition (and, in practice, frontends pick the wrong one). Proven live
    on audit-finding-tracker: PATCH /api/v1/findings/{id} and
    PUT /api/v1/findings/{id}/status both took `StatusUpdate`.

    Body-schema-type equality (not just path overlap) is the signal — apps that
    legitimately have both a general update and an unrelated action route use a
    distinct schema for each (or no body at all on the action route), so they don't
    trip this. Returns a list of error strings (empty = OK).
    """
    errors: list[str] = []
    routers = service_dir / "app" / "routers"
    if not routers.is_dir():
        return errors

    for path in sorted(routers.glob("*.py")):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.relative_to(service_dir).as_posix()

        routes: list[tuple[str, str, str | None]] = []
        for m in _ROUTE_DECORATOR_RE.finditer(text):
            method, url_path = m.group(1), m.group(2)
            if method not in ("patch", "put"):
                continue
            def_match = _DEF_RE.search(text, m.end())
            if not def_match:
                continue
            open_paren = def_match.end() - 1
            close_paren = _matching_close_paren(text, open_paren)
            if close_paren < 0:
                continue
            sig = text[open_paren + 1 : close_paren]
            body_match = _BODY_PARAM_TYPE_RE.search(sig)
            body_type = body_match.group(1) if body_match else None
            routes.append((method, url_path, body_type))

        seen: set[tuple[str, str]] = set()
        for i, (method_a, path_a, body_a) in enumerate(routes):
            if not body_a:
                continue
            for method_b, path_b, body_b in routes[i + 1 :]:
                if body_b != body_a or path_a == path_b:
                    continue
                shorter, longer = sorted((path_a, path_b), key=len)
                if not shorter.endswith("}"):
                    continue  # shorter side must itself be a bare resource-id route
                suffix = longer[len(shorter) :]
                if not suffix.startswith("/") or "/" in suffix[1:] or "{" in suffix:
                    continue  # longer side must add exactly one literal path segment
                key = (shorter, longer)
                if key in seen:
                    continue
                seen.add(key)
                bare_method = method_a if path_a == shorter else method_b
                action_method = method_b if path_a == shorter else method_a
                errors.append(
                    f"{rel}: {bare_method.upper()} {shorter} and {action_method.upper()} {longer} "
                    f"both take `body: {body_a}` — a bare-id route must not clone a dedicated "
                    "action route's request schema. Keep only the dedicated action route, or give "
                    "the bare-id route its own distinct general-update schema."
                )
    return errors


def run_service_validation(
    service: str,
    *,
    run_pytest: bool = True,
    auth_mode: str | None = None,
) -> tuple[bool, str]:
    """Host-side validation gate. Returns (passed, full report).

    auth_mode: explicit override for the auth-mode-aware gates below. Pass this
    whenever calling from outside the LLM tool-call loop — _run_context (which
    _current_auth_mode() reads) is only guaranteed set while run_task()'s
    agent(...) call is in progress; run_task's own `finally` clears it to None
    before returning. main()'s host-validation retry loop calls this function
    AFTER run_task() has already returned, so relying on the global there silently
    defaulted every call to "jwt" regardless of the app's real authMode — this
    parameter is the fix. Defaults to _current_auth_mode() (the global) so the
    dev_validate_app tool, which does run mid-conversation, is unaffected.
    """
    resolved_auth_mode = auth_mode if auth_mode is not None else _current_auth_mode()

    service_dir = _service_dir(service)
    if not service_dir.is_dir():
        return False, f"Error: target-apps/{service}/ does not exist"

    reqs = service_dir / "requirements.txt"
    if not reqs.is_file():
        return False, f"Error: target-apps/{service}/requirements.txt not found"

    python_cmd = _python_for_service(service_dir)

    temp_schema, pg_base_url, setup_errors = setup_temp_pg_test_schema(service_dir, service)
    if setup_errors:
        return False, _format_validation_failure(
            "schema_test_setup", "\n".join(setup_errors), [], []
        )
    env = _validation_env(service_dir, database_url=pg_base_url, postgres_schema=temp_schema)

    try:
        return _run_validation_steps(
            service,
            service_dir,
            python_cmd,
            env,
            run_pytest=run_pytest,
            resolved_auth_mode=resolved_auth_mode,
        )
    finally:
        # Guaranteed cleanup: this finally covers EVERY return path inside
        # _run_validation_steps below (all the early `return _fail(...)` checks,
        # plus the final success return) — not just the pytest step — so a crashed
        # or short-circuited validation run never leaves an orphan schema on shared RDS.
        if temp_schema:
            teardown_temp_pg_schema(temp_schema)


def _run_validation_steps(
    service: str,
    service_dir: Path,
    python_cmd: str,
    env: dict[str, str],
    *,
    run_pytest: bool,
    resolved_auth_mode: str,
) -> tuple[bool, str]:
    """The actual validation checks, run against `env` (real Postgres + throwaway
    schema when db/sql/ exists, built by setup_temp_pg_test_schema). Split out of
    run_service_validation so that function's `finally` guarantees schema teardown
    across every return path here, without wrapping each individual check."""
    import subprocess

    verbose = _validation_verbose()
    checks: list[str] = []
    warnings: list[str] = []
    output_parts: list[str] = []

    def _ok(name: str, verbose_label: str | None = None) -> None:
        checks.append(name)
        if verbose:
            output_parts.append(verbose_label or f"{name.upper()} OK")

    def _warn(message: str) -> None:
        warnings.append(message)
        if verbose:
            output_parts.append(message)

    def _fail(step: str, detail: str) -> tuple[bool, str]:
        if verbose:
            return False, "\n".join(output_parts + [detail])
        return False, _format_validation_failure(step, detail, checks, warnings)

    skip_pip = os.getenv("DEVELOPER_AGENT_SKIP_PIP_SYNC", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if skip_pip:
        _ok("deps (skipped)", "DEPS SKIP (DEVELOPER_AGENT_SKIP_PIP_SYNC)")
    else:
        deps_ok, deps_msg = _ensure_service_requirements_installed(service_dir, python_cmd)
        if not deps_ok:
            return _fail("deps", deps_msg)
        _ok("deps", deps_msg or "DEPS OK")

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
        detail = "STRUCTURE FAILED — missing golden template files:\n" + "\n".join(
            f"  - {f}" for f in missing
        )
        return _fail("structure", detail)
    _ok("structure")

    syntax_errors = _scan_python_syntax(service_dir)
    if syntax_errors:
        detail = (
            "SYNTAX FAILED — files below don't compile (often a literal newline\n"
            "pasted inside a \"...\" string instead of \\n — use \\n or triple-quoted\n"
            "strings for any multi-line text):\n"
        ) + "\n".join(f"  - {e}" for e in syntax_errors)
        return _fail("syntax", detail)
    _ok("syntax")

    try:
        _check_py_encodable(service_dir)
    except ValueError as exc:
        return _fail("py_encodable", str(exc))
    _ok("py_encodable")

    env_results = _validate_env_example(service_dir)
    if env_results[0].startswith("ENV_EXAMPLE FAILED"):
        if verbose:
            output_parts.extend(env_results)
        return _fail("env_example", "\n".join(env_results))
    _ok("env_example")
    if verbose:
        output_parts.extend(env_results)

    antipattern_errors = _scan_router_antipatterns(service_dir)
    if antipattern_errors:
        detail = "ROUTER_ANTIPATTERN FAILED (fix before import will work):\n" + "\n".join(
            f"  - {e}" for e in antipattern_errors
        )
        return _fail("router_antipattern", detail)
    _ok("router_antipattern")

    duplicate_action_errors = _scan_duplicate_action_routes(service_dir)
    if duplicate_action_errors:
        detail = "DUPLICATE_ACTION_ROUTE FAILED (redundant clone of a dedicated action route):\n" + "\n".join(
            f"  - {e}" for e in duplicate_action_errors
        )
        return _fail("duplicate_action_route", detail)
    _ok("duplicate_action_route")

    from _shared.validate_conftest import validate_conftest

    conftest_errors = validate_conftest(service_dir)
    if conftest_errors:
        detail = "CONFTEST FAILED (fix before pytest):\n" + "\n".join(
            f"  - {e}" for e in conftest_errors
        )
        return _fail("conftest", detail)
    _ok("conftest")

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
                        _repo_python_for_shared_tools(),
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
                        return _fail(
                            "seed_bcrypt",
                            "SEED_BCRYPT FAILED — __BCRYPT_PLACEHOLDER__ without documented "
                            f"password in SQL comment (add `-- Password for all seed users: \"…\"`):\n{detail}",
                        )
                    _warn(
                        "seed_bcrypt: hash mismatch or antipattern (non-blocking; "
                        "check whether apply_sql_to_rds.py ran)"
                    )
                else:
                    _ok("seed_bcrypt")
                    has_placeholders = any(
                        "__BCRYPT_PLACEHOLDER__" in p.read_text(encoding="utf-8", errors="replace")
                        for p in seed_sql
                        if "fix" not in p.name.lower()
                    )
                    if has_placeholders:
                        _warn(
                            "seed SQL uses __BCRYPT_PLACEHOLDER__ — RDS login will 401 until "
                            f"apply_sql_to_rds.py runs (`python scripts/apply_sql_to_rds.py --target-app {service}`); "
                            "README should list demo credentials only, not placeholder internals"
                        )
            except subprocess.TimeoutExpired:
                _warn("seed_bcrypt check timed out (non-blocking)")

    # SHA-256 opaque API-key seeds (same gate as bcrypt placeholders — blocks invented sha256_* fakes)
    if seed_sql:
        from _shared.sha256_api_keys import (
            collect_documented_api_keys,
            seed_sql_has_sha256_work,
            validate_seed_sha256_api_keys,
        )

        sha_errors = validate_seed_sha256_api_keys(service_dir / "db" / "sql")
        if sha_errors:
            detail = "SEED_SHA256 FAILED (opaque API-key digests):\n" + "\n".join(
                f"  - {e}" for e in sha_errors
            )
            return _fail("seed_sha256", detail)
        if seed_sql_has_sha256_work(service_dir):
            documented = collect_documented_api_keys(service_dir)
            readme = service_dir / "README.md"
            env_ex = service_dir / ".env.example"
            corpus = ""
            if readme.is_file():
                corpus += readme.read_text(encoding="utf-8", errors="replace")
            if env_ex.is_file():
                corpus += "\n" + env_ex.read_text(encoding="utf-8", errors="replace")
            missing = [
                f'{label}="{raw}"'
                for label, raw in documented.items()
                if raw and raw not in corpus
            ]
            if missing:
                return _fail(
                    "seed_sha256",
                    "SEED_SHA256 FAILED — README/.env.example missing documented API key "
                    "plaintext(s) from seed comments "
                    f"(must match `-- API key for <label>: \"…\"` exactly):\n  - "
                    + "\n  - ".join(missing),
                )
            _ok("seed_sha256")
            _warn(
                "seed SQL uses __SHA256_PLACEHOLDER — RDS login will 401 until "
                f"apply_sql_to_rds.py runs (`python scripts/apply_sql_to_rds.py --target-app {service}`); "
                "README should list the documented API key plaintext only"
            )
        else:
            _ok("seed_sha256")

    from _shared.validate_rds_parity import validate_rds_parity, validate_rds_parity_warnings

    rds_errors = validate_rds_parity(service_dir)
    if rds_errors:
        detail = "RDS_PARITY FAILED (blocks RDS smoke / Streamlit — pytest may still pass):\n" + "\n".join(
            f"  - {e}" for e in rds_errors
        )
        return _fail("rds_parity", detail)
    _ok("rds_parity")
    auth_mode = resolved_auth_mode
    users_auth_errors = validate_users_auth_columns(service_dir, auth_mode)
    if users_auth_errors:
        detail = "\n".join(f"  - {e}" for e in users_auth_errors)
        return _fail("users_auth_columns", detail)
    _ok("users_auth_columns")
    main_auth_errors = validate_main_registers_auth(service_dir, auth_mode)
    if main_auth_errors:
        detail = "\n".join(f"  - {e}" for e in main_auth_errors)
        return _fail("main_registers_auth", detail)
    _ok("main_registers_auth")
    me_fixes = autofix_main_registers_me(service_dir, auth_mode)
    for fix in me_fixes:
        _warn(f"main_registers_me: {fix}")
    main_me_errors = validate_main_registers_me(service_dir, auth_mode)
    if main_me_errors:
        detail = "\n".join(f"  - {e}" for e in main_me_errors)
        return _fail("main_registers_me", detail)
    _ok("main_registers_me")
    cors_errors = validate_cors_configured(service_dir)
    if cors_errors:
        detail = "CORS_CONFIGURED FAILED (browser preflight OPTIONS requests will 405):\n" + "\n".join(
            f"  - {e}" for e in cors_errors
        )
        return _fail("cors_configured", detail)
    _ok("cors_configured")
    auth_mode_file_errors = validate_auth_mode_files(service_dir, auth_mode)
    if auth_mode_file_errors:
        detail = f"AUTH_MODE_FILES FAILED (authMode={auth_mode}):\n" + "\n".join(
            f"  - {e}" for e in auth_mode_file_errors
        )
        return _fail("auth_mode_files", detail)
    _ok("auth_mode_files")
    if auth_mode == "api-key":
        api_key_usage_errors = validate_api_key_route_usage(service_dir)
        if api_key_usage_errors:
            detail = "API_KEY_ROUTE_USAGE FAILED:\n" + "\n".join(
                f"  - {e}" for e in api_key_usage_errors
            )
            return _fail("api_key_route_usage", detail)
        _ok("api_key_route_usage")
        invented_header_errors = validate_no_invented_auth_headers(service_dir, auth_mode)
        if invented_header_errors:
            detail = "NO_INVENTED_AUTH_HEADERS FAILED:\n" + "\n".join(
                f"  - {e}" for e in invented_header_errors
            )
            return _fail("no_invented_auth_headers", detail)
        _ok("no_invented_auth_headers")
    schema_parity_errors, schema_parity_warnings = validate_schema_parity(service_dir)
    if schema_parity_errors:
        detail = "SCHEMA_PARITY FAILED (applied DB vs ORM models):\n" + "\n".join(
            f"  - {e}" for e in schema_parity_errors
        )
        return _fail("schema_parity", detail)
    _ok("schema_parity")
    for warn in schema_parity_warnings:
        _warn(warn)
    for warn in validate_rds_parity_warnings(service_dir):
        _warn(f"rds_parity: {warn}")

    from _shared.validate_orm_relationships import validate_orm_relationships

    orm_rel_errors = validate_orm_relationships(
        service_dir, python_cmd=python_cmd, run_mapper_check=True
    )
    if orm_rel_errors:
        detail = "ORM_RELATIONSHIPS FAILED (M2M / mapper init — list/CRUD would 500):\n" + "\n".join(
            f"  - {e}" for e in orm_rel_errors
        )
        return _fail("orm_relationships", detail)
    _ok("orm_relationships")

    from _shared.validate_ui_parity import (
        autofix_streamlit_api_path_slashes,
        autofix_streamlit_width_api,
        validate_ui_parity,
        validate_ui_parity_blocking,
    )

    width_fixes = autofix_streamlit_width_api(service_dir)
    for fix in width_fixes:
        _warn(f"ui_parity: auto-fixed deprecated Streamlit width API: {fix}")

    slash_fixes = autofix_streamlit_api_path_slashes(service_dir)
    for fix in slash_fixes:
        _warn(f"ui_parity: auto-fixed double-slash Streamlit API path: {fix}")

    ui_errors = validate_ui_parity_blocking(service_dir, _REPO_ROOT)
    if ui_errors:
        detail = "UI_PARITY FAILED (API vs design / Streamlit coverage):\n" + "\n".join(
            f"  - {e}" for e in ui_errors
        )
        return _fail("ui_parity", detail)
    _ok("ui_parity")
    for msg in validate_ui_parity(service_dir, _REPO_ROOT):
        if " WARN:" in msg:
            _warn(f"ui_parity: {msg}")

    # PART 4b: additive, WARN-only completeness check (built app vs design doc).
    # Never blocks — deliberately not gated behind `if completeness_errors: return _fail(...)`
    # anywhere. See _shared/validate_completeness.py for why this exists alongside the
    # (blocking) check_design_routes_implemented above.
    from _shared.validate_completeness import check_completeness_against_design

    for warn in check_completeness_against_design(service_dir, _REPO_ROOT):
        _warn(warn)

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
                detail = "STARTUP_CONFIG FAILED (uvicorn would refuse to start):\n{}{}".format(
                    result.stdout, result.stderr
                )
                return _fail("startup_config", detail)
            _ok("startup_config")
        except subprocess.TimeoutExpired:
            return _fail("startup_config", "STARTUP_CONFIG TIMEOUT")

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
            detail = "IMPORT FAILED (exit code {}):\n{}{}".format(
                result.returncode,
                result.stdout,
                result.stderr,
            )
            if "Cannot specify `Depends` in `Annotated`" in result.stderr:
                detail += (
                    "\nHint: remove `= Depends()` from CurrentUser/DbSession parameters"
                )
            if "parameter without a default follows parameter with a default" in result.stderr:
                detail += (
                    "\nHint: move CurrentUser/DbSession before Query(...) parameters"
                )
            return _fail("import", detail)
        _ok("import")
    except subprocess.TimeoutExpired:
        return _fail("import", "IMPORT TIMEOUT (>30s)")

    health_routes = 0
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
            detail = "HEALTH FAILED:\n{}{}".format(result.stdout, result.stderr)
            return _fail("health", detail)
        health_stdout = result.stdout.strip()
        health_routes = health_stdout.count("API_ROUTE_OK")
        if verbose:
            output_parts.append(health_stdout or "HEALTH OK")
        _ok("health")
    except subprocess.TimeoutExpired:
        return _fail("health", "HEALTH TIMEOUT (>45s)")

    pytest_summary: str | None = None
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
                pytest_summary = _extract_pytest_summary(stdout)
                if verbose:
                    output_parts.append(f"PYTEST OK:\n{stdout}")
                _ok("pytest")
            else:
                detail = f"PYTEST FAILED (exit {result.returncode}):\n{stdout}\n{stderr}"
                if "SQLite Date type only accepts Python date objects" in stdout + stderr:
                    detail += (
                        "\nHint: use date(2024, 1, 1) in ORM fixtures, not '2024-01-01' strings"
                    )
                return _fail("pytest", detail)
        except subprocess.TimeoutExpired:
            return _fail("pytest", "PYTEST TIMEOUT (>180s)")
    elif run_pytest:
        _ok("pytest (skipped — no tests/)")
        if verbose:
            output_parts.append("PYTEST SKIPPED: no tests/ directory")

    if verbose:
        return True, "\n".join(output_parts)
    return True, _format_validation_success(
        checks,
        warnings,
        pytest_summary=pytest_summary,
        health_routes=health_routes,
    )


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

with TestClient(app, raise_server_exceptions=False) as client:
    # 1. Health check
    for path in ("/health", "/healthz"):
        resp = client.get(path)
        if resp.status_code in (200, 503):
            print(f"HEALTH_OK path={path} status={resp.status_code} body={resp.json()}")
            break
    else:
        raise SystemExit("No working health endpoint at /health or /healthz")

    # 2. CORS preflight — every generated app ships a browser frontend that sends
    # a custom auth header (X-API-Key or Authorization), so the browser always
    # preflights with OPTIONS first. Starlette 405s OPTIONS on routes with no
    # CORSMiddleware registered, silently breaking the frontend while curl/pytest
    # (no Origin header) keep passing. This runs the ASGI app directly, so it
    # catches real runtime behavior, not just source-level wiring.
    preflight = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-api-key",
        },
    )
    allow_origin = preflight.headers.get("access-control-allow-origin")
    if preflight.status_code != 200 or not allow_origin:
        raise SystemExit(
            f"CORS_PREFLIGHT_FAILED status={preflight.status_code} "
            f"headers={dict(preflight.headers)} — CORSMiddleware is missing or "
            "misconfigured in app/main.py (browser OPTIONS preflight would 405; "
            "see target-apps/_template/app/main.py or main_apikey.py)"
        )
    print(f"CORS_PREFLIGHT_OK status={preflight.status_code} allow-origin={allow_origin}")

    # 3. Auto-discover GET routes from OpenAPI and smoke-test them
    api_key = os.environ.get("API_KEY", "test-key")
    headers = {"X-API-Key": api_key}
    tested = 0
    openapi = client.get("/openapi.json")
    if openapi.status_code == 200:
        spec = openapi.json()
        # --- ADDED: persist the spec so the frontend agent can read it ---
        _openapi_out = os.path.join(os.getcwd(), "openapi.json")
        with open(_openapi_out, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2)
        print(f"OPENAPI_SAVED path={_openapi_out}")
        # --- end added ---
        for route_path, methods in spec.get("paths", {}).items():
            if route_path in ("/health", "/healthz", "/", "/openapi.json", "/docs", "/redoc"):
                continue
            if "get" not in methods:
                continue
            if "{" in route_path:
                continue
            try:
                resp = client.get(route_path, headers=headers)
                status = resp.status_code
                ok = status in (200, 401, 403, 404, 422, 500)
                tag = "API_ROUTE_OK" if ok else "API_ROUTE_WARN"
                print(f"{tag} GET {route_path} status={status}")
            except Exception as probe_exc:
                # A route handler that raises (e.g. empty test DB: no such table)
                # means the route is wired and reachable — the crash is the empty
                # SQLite fixture, not a health defect. Treat as non-fatal.
                print(f"API_ROUTE_OK GET {route_path} raised={type(probe_exc).__name__} (empty-DB, non-fatal)")
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
    Do NOT declare success to the user until you see VALIDATION PASSED.
    """
    passed, report = run_service_validation(service, run_pytest=run_pytest)
    if passed:
        return report + "\n\nVALIDATION PASSED — safe to hand off."
    return report + "\n\nVALIDATION FAILED — fix all errors above and call dev_validate_app again."


def _auto_validate_enabled() -> bool:
    return os.getenv("DEVELOPER_AGENT_AUTO_VALIDATE", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _auto_validate_run_pytest() -> bool:
    return os.getenv("DEVELOPER_AGENT_AUTO_VALIDATE_PYTEST", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _summary_has_validation_passed(summary: str) -> bool:
    return "VALIDATION PASSED" in summary and "VALIDATION FAILED" not in summary


def _append_required_validation(summary: str, app: str) -> str:
    """Final safety net when the model did not call dev_validate_app itself."""
    if not _auto_validate_enabled() or _summary_has_validation_passed(summary):
        return summary

    passed, report = run_service_validation(app, run_pytest=_auto_validate_run_pytest())
    marker = "VALIDATION PASSED — safe to hand off." if passed else (
        "VALIDATION FAILED — fix all errors above and call dev_validate_app again."
    )
    validation = f"{report}\n\n{marker}"
    if not passed:
        raise RuntimeError(f"developer-agent validation failed:\n{validation}")
    return f"{summary}\n\n## Auto Validation\n{validation}"


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


_REQUIRED_DELIVERY_FILES = (".env.example", "README.md")


def _ensure_delivery_files(
    app: str,
    written: list[str],
    *,
    context: dict[str, Any] | None,
) -> list[str]:
    """Guarantee .env.example and README.md exist and are tracked for publish."""
    slug = slugify(app)
    service_dir = _service_dir(slug)
    prefix = f"target-apps/{slug}/"
    out = list(written)
    for name in _REQUIRED_DELIVERY_FILES:
        rel = f"{prefix}{name}"
        dest = service_dir / name
        if not dest.is_file():
            src = _TEMPLATE_DIR / name
            if not src.is_file():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        if rel not in out:
            out.append(rel)
        if context is not None:
            write_repo_artifact(_cloud_artifact_rel(rel), dest.read_bytes(), context=context)
    return _dedupe_preserve_order(out)


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


def _write_developer_handoff(
    app: str,
    handoff: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
) -> str:
    """Persist handoff JSON for qa-agent / devops-agent; return repo-relative path."""
    slug = slugify(app)
    rel = developer_handoff_rel_for_app(slug)
    payload = json.dumps(handoff, indent=2) + "\n"
    run_id = resolve_run_id(context)
    if run_id:
        write_repo_artifact(rel, payload, context=context)
        return rel
    PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
    path = PIPELINE_DIR / f"{slug}.developer-handoff.json"
    path.write_text(payload, encoding="utf-8")
    return path.relative_to(_REPO_ROOT).as_posix()


def _build_developer_handoff_payload(
    app: str,
    written: list[str],
    ctx: dict[str, Any],
    *,
    status: str,
) -> dict[str, Any]:
    has_env_example = any(p.endswith(".env.example") for p in written)
    handoff: dict[str, Any] = {
        "writtenFiles": written,
        "targetApp": app,
        "status": status,
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
    return handoff


def _persist_developer_handoff(
    app: str,
    ctx: dict[str, Any],
    written: list[str],
    *,
    status: str,
    error: str | None = None,
) -> str | None:
    """Write a terminal developer handoff, including failures with no output files."""
    if not written and status != "failed":
        return None
    handoff = _build_developer_handoff_payload(app, written, ctx, status=status)
    if error:
        handoff["error"] = error
    rel = _write_developer_handoff(app, handoff, context=ctx)
    logger.info(
        "[developer-agent] handoff persisted: %s (%d files, status=%s)",
        rel,
        len(written),
        status,
    )
    return rel


def _frontend_handoff_rel_for_app(app: str) -> str:
    """Developer->Frontend handoff path (Pass 1) — a NEW artifact, sibling of
    openapi.json, using openapi_rel_for_app's exact per-mode formula (S3 key
    ``<slug>/frontend-handoff.json`` vs local ``target-apps/<slug>/frontend-handoff.json``).
    Deliberately not developer_handoff_rel_for_app's path (agents/pipeline/... locally,
    handoffs/... in S3) — that path is reserved for the existing developer-handoff.json
    this artifact must never collide with or overwrite.
    """
    slug = slugify(app)
    if _is_cloud_store():
        return f"{slug}/frontend-handoff.json"
    return f"{target_app_root_rel(slug)}/frontend-handoff.json"


def _build_frontend_handoff_payload(
    app: str,
    ctx: dict[str, Any],
    *,
    status: str,
) -> dict[str, Any]:
    """Build the Developer->Frontend handoff (Pass 1) — the exact snake_case contract
    frontend_agent.py's handle_developer_handoff() already expects (target_app, run_id,
    openapi_path, frontend_required, plus the new backend_path/frontend_folder/framework/
    auth/ui_requirements fields). Every value here is read from ctx, never recomputed:
    status/auth/ui_requirements are passed through as-is, and openapi_path/backend_path
    reuse the same pointers openApiPath/targetAppDir already hold this run. The
    ``or openapi_rel_for_app(slug)``/``or target_app_root_rel(slug)`` fallbacks are not
    a second source of truth — they call the identical deterministic helper ctx's own
    value was assigned from, so they only guard the case where this builder runs from
    the isolated except-path before ctx["openApiPath"]/["targetAppDir"] were set;
    the value produced is always the same either way.
    """
    slug = slugify(app)
    delivery_profile = ctx.get("deliveryProfile") or {}
    frontend_required = delivery_profile.get("requiresReact")
    if frontend_required is None:
        frontend_required = True
    payload: dict[str, Any] = {
        "status": status,
        "target_app": slug,
        "openapi_path": ctx.get("openApiPath") or openapi_rel_for_app(slug),
        "backend_path": ctx.get("targetAppDir") or target_app_root_rel(slug),
        "frontend_folder": f"{target_app_root_rel(slug)}/frontend",
        "framework": "fastapi",
        "auth": str(ctx.get("authMode") or "jwt").strip().lower(),
        "ui_requirements": delivery_profile,
        "frontend_required": bool(frontend_required),
    }
    run_id = str(ctx.get("runId") or ctx.get("run_id") or "").strip()
    if run_id:
        payload["run_id"] = run_id
        payload["runId"] = run_id
    return payload


def _write_frontend_handoff(
    app: str,
    handoff: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
) -> str:
    """Persist the Developer->Frontend handoff (Pass 1) — a NEW artifact written via
    write_repo_artifact's existing local/S3 branching (same helper _enrich_developer_context
    and others already use), so it lands next to openapi.json in both modes without any
    new path logic. Never touches _write_developer_handoff's file or return value."""
    rel = _frontend_handoff_rel_for_app(app)
    payload = json.dumps(handoff, indent=2) + "\n"
    write_repo_artifact(rel, payload, context=context)
    return rel


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


def _coding_model_id(ctx: dict[str, Any] | None = None) -> str:
    """Model for this run; pipeline retries pass codingModelOverride (Sonnet fallback)."""
    if ctx:
        override = str(ctx.get("codingModelOverride") or "").strip()
        if override:
            return override
    return coding_model_id()


def _coding_model(ctx: dict[str, Any] | None = None) -> BedrockModel:
    read_timeout = int(os.getenv("BEDROCK_READ_TIMEOUT", "600"))
    model_id = _coding_model_id(ctx)
    is_override = model_id != coding_model_id()
    model_kwargs: dict[str, Any] = {
        "model_id": model_id,
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
    # Thinking budgets are tuned for the primary coding model; skip them on the
    # Sonnet fallback override unless that model also has thinking enabled.
    if _thinking_enabled() and not is_override:
        # "adaptive" thinking is only supported on Claude 4.5+; Sonnet 4 requires "enabled"|"disabled".
        model_kwargs["additional_request_fields"] = {
            "thinking": {"type": "enabled", "budget_tokens": _thinking_budget_tokens()},
        }

    # Sonnet 4.6 uses THINKING_TYPE=adaptive when DEVELOPER_AGENT_THINKING=1 (see .env.example).
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
        model=_coding_model(ctx),
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
    from _shared.artifact_store import enrich_db_paths_from_run, resolve_run_id
    from _shared.pipeline_context import db_handoff_rel_for_app

    app = slugify(str(ctx["targetApp"]))
    app_root = _REPO_ROOT / target_app_root_rel(app)
    service_dir = _REPO_ROOT / "target-apps" / app

    if resolve_run_id(ctx):
        enrich_db_paths_from_run(ctx)

    # Database-agent handoff file (agents/pipeline/<app>.database-handoff.md; legacy
    # runs wrote it under the app's own db/ dir instead)
    if not ctx.get("databaseHandoffPath"):
        for candidate in (
            _REPO_ROOT / db_handoff_rel_for_app(app),
            app_root / "db" / "HANDOFF.md",
            service_dir / "db" / "HANDOFF.md",
            service_dir / "db" / "handoff.md",
            service_dir / "db" / "database_handoff.md",
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
            (app_root / "db" / "nosql").is_dir()
            or (service_dir / "db" / "nosql").is_dir()
            or ctx.get("preferredNoSqlPath")
        )
        if has_sql and has_nosql:
            ctx["dbBackend"] = "postgres+mongodb"
        elif has_nosql:
            ctx["dbBackend"] = "mongodb"
        elif has_sql:
            ctx["dbBackend"] = "postgres"

    if not ctx.get("templateDir") and _TEMPLATE_DIR.is_dir() and any(_TEMPLATE_DIR.iterdir()):
        try:
            ctx["templateDir"] = _TEMPLATE_DIR.relative_to(_REPO_ROOT).as_posix()
        except ValueError:
            ctx["templateDir"] = "target-apps/_template"


def _build_context(
    *,
    target_app: str,
    jira_key: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    slug = slugify(target_app)
    root_rel = target_app_root_rel(slug)
    if not _is_cloud_store():
        _ensure_service_exists(target_app)
    ctx: dict[str, Any] = {
        "targetApp": slug,
        "targetAppDir": root_rel,
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
    global _written_files, _run_context
    _written_files = []
    _run_context = None

    app = _resolve_target_app(target_app, context)
    base_ctx = dict(context) if context is not None else _build_context(target_app=app, jira_key=jira_key)
    base_ctx.setdefault("targetApp", app)
    ctx = merge_run_handoff_context(base_ctx, include_db_paths=True)
    if _is_cloud_store():
        ctx["targetAppDir"] = target_app_root_rel(app)
    else:
        ctx.setdefault("targetAppDir", _ensure_service_exists(app).relative_to(_REPO_ROOT).as_posix())

    _enrich_developer_context(ctx)

    if jira_key:
        ctx.setdefault("jiraKey", jira_key)
    
    _run_context = ctx

    telemetry: RunTelemetry | None = None
    summary = ""
    handoff_rel: str | None = None
    written: list[str] = []
    agent_error: BaseException | None = None

    try:
        telemetry = RunTelemetry(
            AGENT_NAME,
            target_app=app,
            model_id=_coding_model_id(ctx),
            run_id=str(ctx.get("runId") or ctx.get("run_id") or "").strip() or None,
        )
        agent = _build_agent(ctx, telemetry=telemetry)
        summary = _strip_duplicate_handoff_sections(str(agent(_user_message(task, ctx))))
        try:
            _derive_msg = derive_enums_for_app(app)
            print(_derive_msg)
        except Exception as _e:
            print(f"[derive-enums] {app}: unexpected error (non-fatal): {_e!r}")
        summary = _append_required_validation(summary, app)
    except BaseException as exc:
        agent_error = exc
    finally:
        written = _dedupe_preserve_order(_written_files)
        # A validation failure with no Python exception used to still write
        # status="completed" — gitlab-agent (local) and classify_developer_readiness
        # (cloud) both treat "completed" as "safe to publish", so broken code (missing
        # imports, syntax errors) flowed straight through to GitLab and devops-agent.
        # Reuse the same terminal-failure contract classify_developer_readiness already
        # enforces for status in {"failed", "error"}.
        validation_failed = (
            agent_error is None
            and _auto_validate_enabled()
            and not _summary_has_validation_passed(summary)
        )
        try:
            if written:
                written = _ensure_delivery_files(app, written, context=ctx)
            # Upload openapi.json BEFORE developer-handoff so the orchestrator's
            # handoff gate cannot race ahead of frontend-agent's S3 openapi fetch.
            run_id_early = resolve_run_id(ctx)
            openapi_local = _service_dir(app) / "openapi.json"
            if run_id_early and openapi_local.is_file():
                ctx.setdefault("runId", run_id_early)
                ctx["openApiPath"] = openapi_rel_for_app(app)
                try:
                    _upload_openapi_artifact_if_s3(app, run_id_early)
                except Exception:
                    logger.exception(
                        "[developer-agent] early openapi S3 upload failed (will retry at end)"
                    )
            handoff_status = "failed" if (agent_error or validation_failed) else "completed"
            handoff_error = (
                str(agent_error) if agent_error
                else "dev_validate_app failed — see summary for VALIDATION FAILED report"
                if validation_failed
                else None
            )
            handoff_rel = _persist_developer_handoff(
                app,
                ctx,
                written,
                status=handoff_status,
                error=handoff_error,
            )
            if handoff_rel:
                ctx["developerHandoffPath"] = handoff_rel
            # Pointer only, mirrors developerHandoffPath above: set the path once
            # the file is confirmed on disk, never the spec content itself.
            if (_service_dir(app) / "openapi.json").is_file():
                ctx["openApiPath"] = openapi_rel_for_app(app)
        except Exception as exc:
            logger.exception("[developer-agent] failed to finalize developer handoff")
            if agent_error is None:
                agent_error = exc
            try:
                handoff_rel = _persist_developer_handoff(
                    app,
                    ctx,
                    written,
                    status="failed",
                    error=str(agent_error),
                )
            except Exception:
                logger.exception("[developer-agent] failed to persist failure handoff")
        # Pass 1 of the strict developer->frontend handoff (additive-only): a NEW
        # artifact, never touches developer-handoff.json or any existing context.json
        # key. Isolated in its own try/except, deliberately outside the try/except
        # above, so a bug in this brand-new code path can never flip an
        # otherwise-successful run to "failed" (agent_error) or block the existing
        # developer-handoff.json / telemetry finalization below it — that would be
        # exactly the regression to existing behavior this addition must not cause.
        try:
            if (_service_dir(app) / "openapi.json").is_file():
                frontend_handoff_status = "failed" if (agent_error or validation_failed) else "completed"
                frontend_handoff = _build_frontend_handoff_payload(
                    app, ctx, status=frontend_handoff_status
                )
                _write_frontend_handoff(app, frontend_handoff, context=ctx)
        except Exception:
            logger.exception("[developer-agent] failed to persist frontend handoff (non-fatal)")
        # Telemetry must persist even when the agent run fails — tokens were billed
        # either way, and the control-plane cost breakdown needs every agent reported.
        if telemetry is not None:
            telemetry.extra = {
                "filesWritten": len(written),
                "pattern": _select_pattern_keys(ctx) or "all",
                "status": "failed" if agent_error else "completed",
            }
            try:
                telemetry.finalize(context=ctx)
            except Exception:
                logger.exception("[developer-agent] failed to persist telemetry")
        _run_context = None

    if agent_error is not None:
        raise agent_error

    assert telemetry is not None

    run_id = resolve_run_id(ctx)
    if run_id:
        ctx.setdefault("runId", run_id)
        put_context(run_id, ctx)
        _upload_openapi_artifact_if_s3(app, run_id)

    return summary, written, handoff_rel


def _upload_openapi_artifact_if_s3(app: str, run_id: str) -> None:
    """Mirror context.json's own S3 upload for the OpenAPI spec.

    Health-smoke (run_service_validation, already completed by the time run_task's
    tail reaches this call, via dev_validate_app or _append_required_validation)
    writes openapi.json to local disk (~line 3678) via a bare open() with no S3
    awareness at all. This lands it in S3 too, as a sibling of context.json
    (<slug>/openapi.json), so the frontend agent's S3 fetch-by-slug finds it.

    is_file() guard: skip silently if health-smoke never got this far (app failed
    to start) — that's an existing failure surfaced elsewhere, not a new one to
    invent here. No try/except once the file IS present: matches put_context's own
    fatal-on-failure behavior at its call site immediately above.
    """
    if not is_s3_store():
        return
    openapi_local_path = _service_dir(app) / "openapi.json"
    if not openapi_local_path.is_file():
        return
    put_artifact(
        run_id,
        f"{slugify(app)}/openapi.json",
        openapi_local_path.read_bytes(),
        content_type="application/json",
    )


def parse_task_and_context(message: str) -> tuple[str, dict[str, Any]]:
    """Split orchestrator/A2A messages into task text and context JSON."""
    marker = "\n\nContext:\n"
    if marker in message:
        task, rest = message.rsplit(marker, 1)
        try:
            parsed = json.loads(rest)
            if isinstance(parsed, dict):
                return task.strip(), parsed
        except json.JSONDecodeError:
            pass
    return message.strip(), {}


def _prompt_to_text(message: Any) -> str:
    if isinstance(message, str):
        return message
    if isinstance(message, list):
        parts: list[str] = []
        for item in message:
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(message)


def _developer_async_enabled() -> bool:
    """Fire-and-forget mode on AgentCore (opt-out: AGENTCORE_DEVELOPER_ASYNC=false).

    Synchronous InvokeAgentRuntime request/response is capped at ~15 minutes;
    developer runs regularly exceed that. In async mode the entrypoint acks
    immediately, the implementation continues on a background thread (session
    kept alive via HealthyBusy pings), and the orchestrator polls the developer
    handoff in the run store instead of holding the connection open.
    """
    raw = os.getenv("AGENTCORE_DEVELOPER_ASYNC", "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    return bool(os.getenv("AGENTCORE_AGENT", "").strip())


def _start_developer_pipeline_async(task: str, ctx: dict[str, Any]) -> str | None:
    """Ack immediately and run the developer pipeline on a background thread.

    Returns the ack text, or None when async is unavailable for this request
    (disabled, no runId, or not an S3-backed run) so the caller runs sync.
    """
    run_id = resolve_run_id(ctx)
    if not (_developer_async_enabled() and run_id and is_s3_store()):
        return None
    try:
        app = _resolve_target_app(None, ctx)
    except (ValueError, TargetAppRequiredError):
        return None  # sync path produces the descriptive usage error

    # Write the in_progress handoff BEFORE acking so the orchestrator's poll
    # never observes a stale terminal handoff from a previous attempt.
    ctx = dict(ctx)
    ctx.setdefault("runId", run_id)
    handoff = _build_developer_handoff_payload(app, [], ctx, status="in_progress")
    handoff["asyncAccepted"] = True
    rel = _write_developer_handoff(app, handoff, context=ctx)

    from _shared.background_tasks import run_in_background

    def _background_run() -> None:
        # run_task persists the terminal handoff (completed/failed) in its
        # finally block, so a crash here is still visible to the orchestrator.
        run_task(task, ctx)

    run_in_background(f"developer-agent:{run_id}", _background_run)
    logger.info(
        "[developer-agent] async run accepted: runId=%s app=%s handoff=%s", run_id, app, rel
    )
    return (
        "PIPELINE_ASYNC_STARTED developer-agent\n"
        f"- runId: {run_id}\n"
        f"- targetApp: {app}\n"
        f"- handoff: runs/{run_id}/{rel} (status=in_progress; poll until completed/failed)\n"
        "Implementation continues in the background on this runtime session."
    )


def _execute_developer_pipeline_message(message: Any) -> str:
    """AgentCore A2A: parse Context, run_task (sets _run_context for S3 writes)."""
    text = _prompt_to_text(message)
    from _shared.control_plane_health import is_control_plane_health_check

    if is_control_plane_health_check(text):
        return "OK"
    task, ctx = parse_task_and_context(text)
    if not task.strip():
        task = DEFAULT_PIPELINE_TASK
    if ctx.get("fullRegen"):
        _clear_app_tree(_resolve_target_app(None, ctx))
    async_ack = _start_developer_pipeline_async(task, ctx)
    if async_ack is not None:
        return async_ack
    try:
        summary, written, handoff_rel = run_task(task, ctx or None)
    except (ValueError, TargetAppRequiredError, SystemExit) as exc:
        from _shared.pipeline_context import db_handoff_rel_for_app

        app = (ctx or {}).get("targetApp") or "your-app"
        run_id = resolve_run_id(ctx) or "smoke-001"
        root = target_app_root_rel(str(app))
        example = {
            "targetApp": app,
            "runId": run_id,
            "designDocPath": f"{root}/docs/design/{app}.md",
            "databaseHandoffPath": db_handoff_rel_for_app(str(app)),
        }
        return (
            "Developer pipeline could not start.\n\n"
            f"Reason: {exc}\n\n"
            "Ensure database-agent ran first and Context includes runId + designDocPath:\n\n"
            f"Context:\n{json.dumps(example, indent=2)}\n"
        )

    lines = [summary]
    if written:
        lines.append(f"\nPersisted {len(written)} file(s) to artifact store:")
        for path in written[:20]:
            lines.append(f"  - {path}")
        if len(written) > 20:
            lines.append(f"  ... and {len(written) - 20} more")
    if handoff_rel:
        lines.append(f"- developerHandoff: {handoff_rel}")
    run_id = resolve_run_id(ctx)
    if run_id:
        lines.append(f"- runId: {run_id}")
        if is_s3_store():
            lines.append(f"- s3Prefix: runs/{run_id}/")
    return "\n".join(lines)


def _agent_result_from_text(text: str) -> Any:
    from strands.agent.agent_result import AgentResult
    from strands.telemetry.metrics import EventLoopMetrics

    return AgentResult(
        stop_reason="end_turn",
        message={"role": "assistant", "content": [{"text": text}]},
        metrics=EventLoopMetrics(),
        state={},
    )


def build_developer_pipeline_agent() -> Agent:
    """AgentCore mode: run_task on each A2A message so dev_write_file uploads to S3."""
    agent = _build_agent()

    def developer_invoke(message: Any, **kwargs: Any) -> str:
        del kwargs
        return _execute_developer_pipeline_message(message)

    async def developer_stream_async(
        prompt: Any = None,
        *,
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        from strands.types._events import AgentResultEvent

        del invocation_state, kwargs
        summary = _execute_developer_pipeline_message(prompt)
        yield AgentResultEvent(result=_agent_result_from_text(summary)).as_dict()

    agent.__call__ = developer_invoke  # type: ignore[method-assign]
    agent.stream_async = developer_stream_async  # type: ignore[method-assign]
    return agent


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
    parser.add_argument(
        "--full-regen",
        action="store_true",
        help=(
            "Set only by the orchestrator: this is a full from-scratch regeneration, "
            "so clear app/, schemas/, tests/, .env before writing. Standalone CLI use "
            "(e.g. a custom --task for a narrow edit) should never pass this."
        ),
    )
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

    extra = merge_run_handoff_context(extra, include_db_paths=True)
    _enrich_developer_context(extra)

    ctx = _build_context(target_app=target, jira_key=args.jira_key, extra=extra or None)

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
        from _shared.pipeline_context import db_handoff_rel_for_app

        print(
            "[developer-agent] DB handoff : (not found — run database-agent first; "
            f"expected {db_handoff_rel_for_app(str(ctx.get('targetApp') or ''))})",
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

    if args.full_regen:
        _clear_app_tree(target)

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
        passed, validate_report = run_service_validation(
            target,
            run_pytest=True,
            auth_mode=str(ctx.get("authMode") or "jwt").strip().lower(),
        )
        if passed:
            print(f"[developer-agent] Host validation passed — {validate_report}", file=sys.stderr)
            break
        print("\n[developer-agent] Host validation FAILED:", file=sys.stderr)
        print(validate_report, file=sys.stderr)
        if attempt >= max_validate_retries:
            print(
                "[developer-agent] Giving up after "
                f"{max_validate_retries + 1} attempt(s) — exiting non-zero.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        task = (
            "Host validation failed after your implementation. Fix ALL blocking errors "
            "before handoff. Call dev_validate_app(run_pytest=True) until you see "
            "VALIDATION PASSED.\n\n"
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