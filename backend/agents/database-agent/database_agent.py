"""Database agent — Strands + Bedrock; SQL migrations/seed and DB handoff."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections.abc import AsyncIterator, Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any
import botocore.config
from a2a.types import AgentSkill
from strands import Agent
from strands.models import BedrockModel
from strands.models.model import CacheConfig
from strands.multiagent.a2a import A2AServer
from strands.tools.decorator import tool
from strands.types.exceptions import MCPClientInitializationError

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.artifact_store import (
    delete_repo_artifact,
    get_artifact,
    is_s3_store,
    list_run_artifact_keys,
    put_context,
    read_repo_artifact,
    resolve_run_id,
    run_sql_artifact_keys,
    write_repo_artifact,
)
from _shared.context_cli import load_context_extra, parse_context_args
from _shared.db_handoff import write_db_handoff
from _shared.env import load_repo_env
from _shared.mcp_clients import mongodb_mcp_client, postgres_mcp_tool_params
from _shared.pipeline_context import (
    TargetAppRequiredError,
    _is_cloud_store,
    cloud_artifact_rel,
    enrich_handoff_context,
    merge_run_handoff_context,
    resolve_cli_context,
    resolve_target_app,
    slugify,
    target_app_root_rel,
)
from _shared.telemetry import RunTelemetry, StrandsTelemetryCallback

_TARGET_APPS = _REPO_ROOT / "target-apps"
_DEFAULT_DB_SUBDIR = "db"


load_repo_env()


AGENT_NAME = "database-agent"
A2A_PORT = 9108

_SEED_MIN_ROWS = os.getenv("SEED_MIN_ROWS", "5")
_SEED_MAX_ROWS = os.getenv("SEED_MAX_ROWS", "10")

DEFAULT_PIPELINE_TASK = """\
Implement the database layer as a DB developer using Context handoff.
1. db_read_file(designDocPath) — §3 (tables) and §6 (migration order + seed).
2. If prdPath is in Context, db_read_file(prdPath) — build the FULL list of distinct entities/concepts
   from design §3 UNION PRD §7 (the brief's own entity list, not just whatever design §3 already has).
   Every entity in that union gets a table UNLESS it is genuinely external-system data that cannot be
   persisted in Postgres/MongoDB (see "PRD / design scope" below) — and any such skip MUST be named
   explicitly in the schema_summary reply, never omitted silently.
3. db_list_tree dbOutputDir; db_write_file idempotent scripts under preferredSqlPath (and nosql/ only if design requires MongoDB).
4. When `applyToRdsAfterWrite` is true in Context: write sql/ only — the host applies files to RDS after this run (do not call postgres_run_query).
   MongoDB MCP (if present): apply nosql/ scripts when design requires document storage.
5. Call `db_validate_sql(service=targetApp)` after writing sql/ — fix every SQL_VALIDATION FAILED before finishing.
6. Reply once: schema_summary, sql_artifacts, handoff_for_developer. Omit execution_commands when applyToRdsAfterWrite is true.
   The host writes the database handoff doc (databaseHandoffPath) after the run — do not db_write_file it yourself.\
"""

_READ_PREFIXES = (
    _TARGET_APPS,
    _REPO_ROOT / "docs",
    _REPO_ROOT / "agents",
    _REPO_ROOT / "inputs",
)

_written_files: list[str] = []
_deleted_files: list[str] = []
_run_context: dict[str, Any] | None = None

_JWT_AUTH_TABLE_SECTION = """\
- - **JWT users table (canonical, required):** the `users` table MUST have these exact columns:
  `id` (PK), `username` (unique, NOT NULL — the login identifier), `password_hash` (NOT NULL — the bcrypt hash column), `role` (NOT NULL). `email` is optional. Use these EXACT names always.
  Do **not** use `hashed_password`, `password`, or other aliases, and do **not** use `email` as the login column — login is always by `username`. Split naming across SQL vs ORM breaks the fixed login router. Seed, HANDOFF, ORM, and developer-agent must reuse `username` + `password_hash` exactly.
- **JWT seed users:** use `__BCRYPT_PLACEHOLDER__` in the `password_hash` column. See **Seeding credentials** below for the three mandatory steps. Never invent `$2b$12$...` strings."""

_API_KEY_AUTH_TABLE_SECTION = """\
- - **API-key users table (canonical, required, hardcoded — not an LLM choice):** the `users` table MUST have these exact columns: `id` (PK), `token` (unique, NOT NULL — the per-user opaque credential sent as the `X-API-Key` header, e.g. `tok_alice`, `tok_bob_admin`), `role` (NOT NULL — at least `employee`/`manager`/`admin`, per design). There is **no shared secret and no `API_KEY` env var** — every caller has their own row. Do **not** use `password_hash`, `username`, `api_key_hash`, or any other column name for the credential; the fixed `require_api_key` dependency (`app/dependencies.py`) reads `token` and `role` by these exact names.
- **API-key seed users:** insert the `token` value as **plaintext** (e.g. `'tok_alice'`) — it is looked up by direct equality, never hashed, never `__BCRYPT_PLACEHOLDER__` (that placeholder is for password hashes only and does not apply here). Seed **multiple users spanning every role** the design's RBAC table requires (at least one `employee`, one `manager`, one `admin` row when those roles exist) so role differences are testable, each with its own distinct token:
  ```sql
  INSERT INTO users (id, token, role) VALUES
      ('uuid-1', 'tok_alice_employee', 'employee'),
      ('uuid-2', 'tok_bob_manager',    'manager'),
      ('uuid-3', 'tok_carol_admin',    'admin');
  ```
  Document these token/role pairs in `HANDOFF.md` under `### seedCredentials` (columns: token | role) so developer-agent's README "Demo accounts" table and QA can reuse them without inventing values."""


def _build_system_prompt(ctx: dict[str, Any] | None = None) -> str:
    """Render DATABASE_SYS_PROMPT with the auth-mode-specific table section.

    Deterministic on context authMode (set by auth_profile.py, never an LLM
    judgment) — defaults to "jwt", byte-identical to the prompt before authMode
    existed. Only authMode == "api-key" swaps in the api-key alternative.
    """
    auth_mode = str((ctx or {}).get("authMode") or "jwt").strip().lower()
    section = _API_KEY_AUTH_TABLE_SECTION if auth_mode == "api-key" else _JWT_AUTH_TABLE_SECTION
    return _DATABASE_SYS_PROMPT_TEMPLATE.replace("{{AUTH_TABLE_SECTION}}", section)


_DATABASE_SYS_PROMPT_TEMPLATE = """\
You are the **database developer** for the SDLC Agentic AI Platform. You run after architect-agent
and before developer-agent. You author migrations and dev seeds; the host applies sql/ to RDS when requested.

## Handoff (read files — not prior agent chat)
| Source | Action | Use |
|--------|--------|-----|
| `designDocPath` | `db_read_file` | **§3** → DDL; **§6** → file order + seed spec |
| "Database contract" block (this message, when present) | Already inlined below — no file read needed | **Authoritative** for table/column/index/FK/relationship/status-enum detail when present; validated JSON from architect-agent. Absent on some runs — design §3/§6 above is always still correct and is your fallback. |
| `prdPath` | `db_read_file` when present | PRD **§7 Core Data Entities** — validate RDS scope |
| `productBrief` | Context JSON | Compact product orientation only |
| `diagramPaths` | Context JSON | Optional; do not parse PNGs |
| `postgresMcpParams` | Context JSON (when `--with-postgres`) | RDS target (endpoint, database) for handoff only |
| `applyToRdsAfterWrite` | Context JSON | When true, write sql/ only; host runs apply script after agent completes |
| `seedMinRows` / `seedMaxRows` | Context JSON | Dev seed row targets per RDS table (see Artifacts) |

## PRD / design scope (required before any DDL) — NO SILENT DROPS

**Rule: every distinct entity/concept described in the brief/PRD/design doc gets a table.**
Build the entity list from the UNION of design **§3** and PRD **§7** (and the raw brief when no PRD
is set) — design §3 is a starting point, not a ceiling. If the PRD/brief names an entity that design
§3 omitted, add the table anyway; do not treat an incomplete design doc as license to under-build.
Do not shrink scope to keep the schema "simple," "minimal," or to hit any particular table count —
there is no target table count. A 15-entity brief should produce roughly 15 tables, not a
convenient-sounding subset.

1. Enumerate every entity/concept in design §3 UNION PRD §7 (or the raw brief) **before writing any
   file**, as a numbered list in your `schema_summary` reply — this is the DB equivalent of a route
   manifest. Every listed entity must then be traceable to either a table, or an explicit skip (rule 2).
2. **The only acceptable reason to skip a table is that the entity is genuinely external-system data
   that cannot be persisted in Postgres/MongoDB** — not "the app doesn't strictly need it" and not
   "to keep the schema small." Known genuine-skip categories:
   - **Cost Record** / CUR line items → Athena + S3 (query at runtime, not migrated here)
   - **External Jira ticket body** → Jira API; app stores link rows only
   - **Executive summary files** → S3; `executive_summaries` holds keys/metadata only
   Two related concepts may legitimately collapse into one table (e.g. a status-history concept
   folded into an `audit_log` table) — that is fine, and is NOT a drop, as long as every source
   entity is still represented by a column or a row type in the table you chose.
3. **Every skip or merge MUST be stated explicitly** in `schema_summary` — one line per skipped/merged
   entity, e.g. `SKIPPED: CostRecord — lives in Athena/S3, not RDS (per design §3 note)` or
   `MERGED: StatusHistory -> audit_log.event_type column`. A skip that is not written out in the
   reply is treated as a dropped entity, not an intentional decision — **silence is not a valid skip.**
4. **`jira_tickets` (FR-6):** required when design §3 lists it — stores `recommendation_id`, `jira_key`, `jira_url`
   after approve. This is the app's foreign link to Jira, not a duplicate of Jira's database.
5. Do not invent tables, columns, or migrations for entities that are not described anywhere in the
   brief/PRD/design doc — this rule is about not padding scope, not about permission to drop scope.

## Artifacts
Under `dbOutputDir` (from Context — typically `<service>/db/` in cloud, `target-apps/<service>/db/` locally):
- Database handoff doc (`databaseHandoffPath`, under `agents/pipeline/`) — **host-written only** after your run (do not `db_write_file` it). Put `### seedCredentials` in your reply so the host can copy it in. Developer-agent reads `databaseHandoffPath`.
- `sql/001_*.sql` … numbered, idempotent DDL (`IF NOT EXISTS` where possible)
- **`SET search_path` rule — applies to every migration file:**
  `apply_sql_to_rds.py` already sets `search_path = <app_schema>, public` at the **connection level** before each file runs.
  - **NEVER write `SET search_path = public` alone** — it overrides the connection setting and hides enums/types created by earlier migrations, causing `type does not exist` at apply time. `db_validate_sql` will block your run if it detects this.
  - Default: **omit `SET search_path` entirely** from all migration files — the connection-level setting is already correct.
  - If you must set it explicitly, always include both schemas: `SET search_path = <app_schema>, public`.
  - `001_enable_pgvector.sql` is the one exception: it must have **no** `SET search_path` at all (per pgvector rule below).
- **Schema-qualified type existence checks — mandatory for DO $$ blocks:**
  Multiple apps share one RDS instance with separate schemas. A bare `IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'my_enum')` checks ALL schemas, not just the current app schema. If `my_enum` already exists in another app's schema (e.g. `inventory_app.user_role`), the check returns TRUE, the DO block skips type creation, and the following `CREATE TABLE` fails with "type does not exist".
  - **Always add a schema filter** using `current_schema()`:
    ```sql
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE t.typname = 'my_enum' AND n.nspname = current_schema()
        ) THEN
            CREATE TYPE my_enum AS ENUM ('a', 'b', 'c');
        END IF;
    END $$;
    ```
  - The apply script auto-patches bare checks as a safety net, but always generate the correct form.
- **Postgres extensions before indexes:** `CREATE EXTENSION IF NOT EXISTS pg_trgm` (and any other extension) must run in an early migration **before** any index using `gin_trgm_ops` or extension-specific operator classes — never only in seed files.
- **`ALTER TABLE ... ADD CONSTRAINT` has NO `IF NOT EXISTS` support in Postgres** — unlike `CREATE TABLE`/`CREATE INDEX`/`CREATE EXTENSION`, `ADD CONSTRAINT IF NOT EXISTS` is a syntax error (`syntax error at or near "EXISTS"`), not a no-op. For an idempotent constraint add, wrap it in a `DO $$` block instead:
  ```sql
  DO $$ BEGIN
      ALTER TABLE users ADD CONSTRAINT fk_users_linked_technician
          FOREIGN KEY (technician_id) REFERENCES technicians (id);
  EXCEPTION WHEN duplicate_object THEN NULL;
  END $$;
  ```
- **pgvector / VECTOR columns (RAG, dedup, semantic search):** When design §2/§3 uses `vector(n)`, HNSW, or cosine similarity:
  - First migration MUST be `001_enable_pgvector.sql` (before any `VECTOR(...)` column or `vector_cosine_ops` index).
  - Use this template verbatim — **do not** `SET search_path` before `CREATE EXTENSION` (RDS requires extension in `public`):
    ```sql
    -- 001_enable_pgvector.sql
    CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;
    ```
  - Reference: `target-apps/_template/db/reference/rag_pgvector_reference.sql`
  - `vector(n)` dimension **must match** the embedding model in design §2 (e.g. 1536 for `amazon.titan-embed-text-v1`, 1024 for v2).
  - HNSW index (after table DDL): `USING hnsw (embedding vector_cosine_ops)` with `CREATE INDEX IF NOT EXISTS`.
  - App-schema `SET search_path` belongs in **later** migrations (enums/tables), not in `001_enable_pgvector.sql`.
  - **Shared RDS:** pgvector must live in `public`. If an older app installed `vector` in its own schema, the host apply script relocates it with `ALTER EXTENSION vector SET SCHEMA public` before DDL.
  - **Seed placeholder embeddings — use one of these idioms:**
    ```sql
    (SELECT array_fill(0.01::real, ARRAY[1024])::vector)
    -- or a bracketed text literal:
    '[0.01,0.01,...]'::vector
    ```
    `array_fill(...)::vector` / `array_agg(...)::vector` cast a native Postgres array — preferred.
    **Never** use `array_to_string` / `string_agg` / `format` / `||` to build CSV text for `::vector`, and never cast a bare `'0.01,0.01,…'` string (must start with `[`). `db_validate_sql` rejects these; fix before finishing.
  - **`api_keys.key_hash` — match the design hash algorithm (MANDATORY):**
    - **bcrypt.verify apps** (e.g. expense-tracker): use `'__BCRYPT_PLACEHOLDER__'` per row. Host
      replaces each with a *distinct* salted bcrypt hash (UNIQUE-safe). Never invent `$2b$12$…`.
    - **SHA-256 hex lookup apps** (`hashlib.sha256(raw).hexdigest()` in dependencies): use
      **labeled** sentinels `'__SHA256_PLACEHOLDER:<label>__'` (label must match the row's
      `label` / name column). Add one comment per key at the top of the seed file:
      `-- API key for demo-standard: "demo-standard-key-2024"`
      Host replaces with the real 64-char hex digest. **Never** invent fake tokens like
      `'sha256_standard_demo_001'` — those are not digests and live UI/Swagger always 401.
      Reference: `target-apps/_template/db/reference/sha256_api_keys_seed_reference.sql`
      (`db_validate_sql` blocks invented `sha256_*` tokens).
    - Do **not** put `__BCRYPT_PLACEHOLDER__` into `key_hash` when the app looks up SHA-256 hex
      (bcrypt strings will never match). Do **not** put SHA-256 placeholders into JWT
      `hashed_password` columns.
- `sql/*_seed.sql` or `011_seed.sql` — **dev/test fixture rows only** per design §6.2 (not production CUR data).
  Use `seedMinRows`–`seedMaxRows` from Context: **every RDS table in §3 must get that many INSERT rows**
  (realistic names/emails/dates; stable UUIDs only where tests need them; respect FK order; `ON CONFLICT DO NOTHING`).
  Do not leave any §3 table empty in seed unless design §6.2 explicitly excludes it.
- **Optional / nullable columns:** When design §3 marks a field optional (e.g. `ends_at`, `description`)
  or seed uses `NULL` for it, DDL must **omit** `NOT NULL`. Call `db_validate_sql` before finishing —
  it blocks NULL inserts into NOT NULL columns. `CREATE TABLE IF NOT EXISTS` does not change nullability
  on existing RDS tables; the host apply script reconciles drift, but your schema files must match design.
- **Multi-value string fields (tags, type lists, codes) — prefer JSONB, not TEXT[]:**
  Developer-agent schema_parity fails when DDL is `TEXT[]` / `UUID[]` but the ORM lands as
  `String`/`Text` (a common LLM slip). Prefer `JSONB NOT NULL DEFAULT '[]'::jsonb` for
  unordered string lists (compatible aircraft types, tags, labels). Developer maps that to
  `mapped_column(JSONB().with_variant(JSON(), "sqlite"), ...)` — already a hard-taught pattern.
  Use native `TYPE[]` only when the design explicitly needs array operators (`ANY`, `@>`, GIN
  on arrays). If you do use `col TEXT[]` / `UUID[]`, list every array column in
  `### handoff_for_developer` as `ARRAY: table.col → ORM ARRAY(String)|ARRAY(PG_UUID)` so
  developer cannot miss it.
{{AUTH_TABLE_SECTION}}
- `nosql/` — **only** when design §3/§6 explicitly requires MongoDB collections

## RDS apply (host — not your job when `applyToRdsAfterWrite` is true)
- **Do not** use `postgres_run_query` to apply migrations. The CLI runs `scripts/apply_sql_to_rds.py` after you finish.
- Write complete, idempotent `sql/` files in §6 order; host applies them to RDS.

## MongoDB MCP (only when attached)
- Apply scripts under `nosql/` when design requires document storage.

## Workflow
1. Read design (+ PRD when `prdPath` set); list planned tables with PRD FR ids.
2. `sql/` is cleared automatically at database-agent startup for local runs (S3/cloud mode skips this) — normally just write the current migration set fresh, and use `db_list_tree` for `nosql/` only if design requires MongoDB. If any stale `sql/` file could survive (cloud mode, or a superseded migration under a different filename), `db_delete_file` it first: `apply_sql_to_rds.py` runs every `*.sql` it finds, so a leftover old migration can win via `CREATE TABLE IF NOT EXISTS` and leave RDS on the old schema. Do not leave duplicate `00N_*.sql` no-ops.
3. Write migrations in §6 order; write seed with `seedMinRows`–`seedMaxRows` rows per §3 table.
4. `db_validate_sql(service=targetApp)` — must report SQL_VALIDATION OK.
5. One compact reply (see below).

## Response format (single pass — no duplication)
Return **once**, using `###` headings in this order:
1. `### schema_summary` — table/collection count, enums, PRD FR mapping (≤12 bullets)
2. `### sql_artifacts` — ordered paths only (table, no prose repeat)
3. `### handoff_for_developer` — DSN pattern, SQLAlchemy/ORM notes, stable seed UUIDs if any (≤8 bullets)
4. `### seedCredentials` — **required when JWT/password seed users exist** (markdown table; see Seeding credentials). Host copies this into the database handoff doc.
5. `### execution_commands` — **omit** when `applyToRdsAfterWrite` is true; include **only** for files-only runs (short apply note)

Do **not** repeat sections. Do **not** paste full SQL bodies in the reply.
Do **not** add a `## Files written` section — the CLI logs written paths on stderr.
Do **not** `db_write_file` the database handoff doc — the host writes it after your reply.
Use **one `db_write_file` call per sql file**; put full SQL only in the tool `content` argument, not in chat text.

## UUID literals in seed SQL — hex digits only
When writing hardcoded UUIDs in seed INSERT rows, **every character must be a valid hex digit** (`0-9`, `a-f`).
Letters `g` through `z` are **invalid** in UUID and will crash `apply_sql_to_rds.py`.

**Good examples:**
```sql
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', ...)
('00000001-0000-0000-0000-000000000001', ...)
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', ...)  -- OK: a is hex
('ffffffff-ffff-ffff-ffff-ffffffffffff', ...)  -- OK: f is hex
```

**Bad — will fail:**
```sql
('gggggggg-gggg-gggg-gggg-gggggggggggg', ...)  -- g is NOT hex
('iiiiiiii-iiii-iiii-iiii-iiiiiiiiiiii', ...)  -- i is NOT hex
```

When you need more than 15 distinct seed IDs (a-f + 0-9 exhausted), use zero-padded counters:
`'00000001-0000-0000-0000-000000000001'`, `'00000002-...'`, etc.

Alternatively, use `gen_random_uuid()` as DEFAULT and omit the `id` column from INSERT.

## Guardrails
- Never write outside `dbOutputDir`.
- Do not modify `docs/design/*.md`, PRD, or secrets.
- No password literals in SQL files.

## Seeding credentials — DO NOT invent hashes

When any seed row has a password hash column (`password_hash` — required for JWT apps), **NEVER write a literal bcrypt/argon/scrypt string**. The LLM cannot compute real hashes; any `$2b$12$...` string you produce will be random characters that fail every `bcrypt.checkpw(...)` call and break login.

### All three steps are MANDATORY — skipping any one causes silent 401 on RDS

**Step 1 — Sentinel value in every seed user row**
Insert `'__BCRYPT_PLACEHOLDER__'` in the `password_hash` column (canonical name). Login is always by `username`. Never invent a different column name.

```sql
INSERT INTO users (id, username, password_hash, role) VALUES
    ('uuid-1', 'alice', '__BCRYPT_PLACEHOLDER__', 'admin'),
    ('uuid-2', 'bob',   '__BCRYPT_PLACEHOLDER__', 'viewer');
```

**Step 2 — Machine-parseable password comment at the TOP of the seed file (MANDATORY)**
The seed file MUST contain this comment. It is parsed by `agents/_shared/materialize_seed_passwords.py` to know which password to hash. Without it, materialize silently skips and every login returns 401.

```sql
-- Password for all seed users: "YourPassword123!"
```

Format rules (regex: `(?:Password|passwords?)[^"\\n]*(?:"([^"]+)"|: *([^\\s!][^\\n]*!))`):
- Must contain the word `Password` (case-insensitive)
- Password must be **double-quoted** `"…"` OR the line must **end with `!`** (e.g. `-- Password: Pass123!`)
- Put it as the first comment in the file, before any `SET search_path` or `INSERT` statements
- One comment covers all users when they share a password; add separate comments when roles have different passwords (first match wins)

**Step 3 — Credential map in your reply under `### seedCredentials` (MANDATORY)**
Put this section in your **chat reply** (Response format). The host copies it into the database handoff doc (`databaseHandoffPath`).
**Do not** `db_write_file` it yourself — that file is host-owned.

```
### seedCredentials
| username | role      | plaintext_password |
|----------|-----------|--------------------|
| alice    | admin     | YourPassword123!   |
| bob      | viewer    | YourPassword123!   |
```
- First column: the `username` value (login is ALWAYS by `username`; `email` is never the login column)
- Third column: the plaintext password (must match the SQL comment exactly)

The host pipeline runs `agents/_shared/materialize_seed_passwords.py` after RDS apply — it reads **Step 2** for the password, then **Step 3** (from HANDOFF, copied from your reply) and/or parses `INSERT INTO users (...)` column order from seed SQL to find which rows to update, then UPDATEs the hash column with a real bcrypt hash computed on CPU.

The seed `INSERT INTO users (...)` column list MUST include `username` and `password_hash`.

Same rule for JWT `hashed_password` (bcrypt placeholder). For **SHA-256 API-key**
`key_hash` columns, use `__SHA256_PLACEHOLDER:<label>__` + `-- API key for <label>: "…"`
comments instead — never invent `sha256_*` fake tokens or literal hex digests.
Mandatory trio: sentinel in SQL + password/API-key comment in seed file + `### seedCredentials` in your reply.
"""

# Backwards-compat alias: jwt-mode prompt (default). Prefer _build_system_prompt(ctx).
DATABASE_SYS_PROMPT = _build_system_prompt(None)


def _service_dir(service: str) -> Path:
    return _TARGET_APPS / slugify(service)


def _ensure_service_exists(service: str) -> Path:
    path = _service_dir(service)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_repo_path(relative_path: str, *, write: bool) -> Path:
    raw = relative_path.strip().replace("\\", "/")
    if not raw:
        raise ValueError("path is required")
    candidate = (_REPO_ROOT / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    if not str(candidate).startswith(str(_REPO_ROOT.resolve())):
        raise ValueError(f"path must stay inside repo: {relative_path}")
    if write:
        under_target_apps = str(candidate).startswith(str(_TARGET_APPS.resolve()))
        if not under_target_apps:
            raise ValueError("writes only allowed under target-apps/")
        return candidate
    allowed = any(str(candidate).startswith(str(prefix.resolve())) for prefix in _READ_PREFIXES)
    if not allowed:
        raise ValueError(f"read not allowed for path: {relative_path}")
    return candidate


@tool
def db_list_tree(service: str, subpath: str = "") -> str:
    """List files under the service app root (optionally under subpath)."""
    prefix = f"{target_app_root_rel(slugify(service))}/"
    if subpath.strip():
        prefix = f"{prefix}{subpath.strip().strip('/')}/"
    ctx = _run_context
    run_id = resolve_run_id(ctx) if ctx else None
    if run_id:
        paths = [
            key
            for key in list_run_artifact_keys(run_id)
            if key.startswith(prefix) and not key.endswith("/")
        ]
        return "\n".join(paths) if paths else "(no files)"

    root = _ensure_service_exists(service)
    base = (root / subpath).resolve()
    if not str(base).startswith(str(root.resolve())):
        return "Error: subpath escapes service directory"
    if not base.exists():
        return f"Error: not found: {base.relative_to(_REPO_ROOT).as_posix()}"
    paths: list[str] = []
    for path in sorted(base.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            paths.append(path.relative_to(_REPO_ROOT).as_posix())
    return "\n".join(paths) if paths else "(no files)"


@tool
def db_read_file(path: str) -> str:
    """Read a file inside allowed repo paths."""
    raw = path.strip().replace("\\", "/")
    ctx = _run_context
    run_id = resolve_run_id(ctx) if ctx else None
    if run_id:
        try:
            return read_repo_artifact(raw, context=ctx).decode("utf-8")
        except FileNotFoundError:
            pass
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
def db_write_file(path: str, content: str) -> str:
    """Write SQL/NoSQL artifacts under the app db tree (cloud: ``<slug>/db/...``)."""
    raw = path.strip()
    artifact_rel = cloud_artifact_rel(raw)
    # Cloud/S3 mode: persist via artifact store only. Never materialize stripped
    # ``<slug>/...`` keys as ``backend/<slug>/...`` on local disk (that created
    # the stale backend/demo-api/ tree).
    if _is_cloud_store():
        if _run_context is None:
            return (
                "Error: cloud write requires active run context "
                "(run_task must set _run_context before db_write_file)."
            )
        run_id = resolve_run_id(_run_context)
        if not run_id:
            return (
                "Error: cloud write requires runId in Context "
                f"(refused to claim write of {artifact_rel})."
            )
        write_repo_artifact(artifact_rel, content, context=_run_context)
        _written_files.append(artifact_rel)
        return f"Wrote {artifact_rel} ({len(content)} bytes)"
    try:
        file_path = _resolve_repo_path(raw, write=True)
    except ValueError as exc:
        return f"Error: {exc}"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8", newline="\n")
    rel = cloud_artifact_rel(file_path.relative_to(_REPO_ROOT).as_posix())
    _written_files.append(rel)
    if _run_context is not None:
        write_repo_artifact(rel, content, context=_run_context)
    return f"Wrote {rel} ({len(content)} bytes)"


@tool
def db_delete_file(path: str) -> str:
    """Delete a superseded generated file under the app db tree (cloud: ``<slug>/db/...``).

    Use this before writing a redesigned schema so old ``sql/`` migrations from an earlier
    generation don't linger alongside the new ones — ``apply_sql_to_rds.py`` runs every
    ``*.sql`` file it finds, and a stale file left behind can silently win over the current
    design via ``CREATE TABLE IF NOT EXISTS``. No-op (not an error) if the file is already gone.
    """
    raw = path.strip()
    artifact_rel = cloud_artifact_rel(raw)
    if _is_cloud_store():
        if _run_context is None:
            return (
                "Error: cloud delete requires active run context "
                "(run_task must set _run_context before db_delete_file)."
            )
        run_id = resolve_run_id(_run_context)
        if not run_id:
            return (
                "Error: cloud delete requires runId in Context "
                f"(refused to claim delete of {artifact_rel})."
            )
        delete_repo_artifact(artifact_rel, context=_run_context)
        _deleted_files.append(artifact_rel)
        return f"Deleted {artifact_rel}"
    try:
        file_path = _resolve_repo_path(raw, write=True)
    except ValueError as exc:
        return f"Error: {exc}"
    file_path.unlink(missing_ok=True)
    rel = cloud_artifact_rel(file_path.relative_to(_REPO_ROOT).as_posix())
    _deleted_files.append(rel)
    if _run_context is not None:
        delete_repo_artifact(rel, context=_run_context)
    return f"Deleted {rel}"


def _format_sql_validation_result(errors: list[str]) -> str:
    if not errors:
        return (
            "SQL_VALIDATION OK — schema/seed nullability, UUID literals, "
            "search_path, and vector seed casts are consistent."
        )
    lines = "\n".join(f"  - {e}" for e in errors)
    return (
        "SQL_VALIDATION FAILED — fix schema or seed before RDS apply:\n"
        f"{lines}\n"
        "Rules: optional columns omit NOT NULL; seed NULL only for nullable columns; "
        "UUIDs hex-only; never SET search_path = public alone; "
        "cast arrays with array_fill(...)::vector (never array_to_string(...)::vector)."
    )


@contextmanager
def _cloud_sql_dir_for_validation(service: str, run_id: str) -> Iterator[Path]:
    """Download run ``db/sql/*.sql`` into a temp dir for validate_sql_dir."""
    slug = slugify(service)
    keys = run_sql_artifact_keys(run_id, slug)
    if not keys:
        raise FileNotFoundError(
            f"no SQL artifacts in run {run_id} under {slug}/db/sql/ "
            f"(or target-apps/{slug}/db/sql/)"
        )
    with tempfile.TemporaryDirectory(prefix="db-sql-validate-") as tmp:
        sql_dir = Path(tmp) / "sql"
        sql_dir.mkdir(parents=True)
        for key in keys:
            name = Path(key).name
            if not name.lower().endswith(".sql"):
                continue
            (sql_dir / name).write_bytes(get_artifact(run_id, key))
        if not any(sql_dir.glob("*.sql")):
            raise FileNotFoundError(
                f"run {run_id} listed SQL keys but none were writable as *.sql files"
            )
        yield sql_dir


@tool
def db_validate_sql(service: str) -> str:
    """Validate db/sql/ (local disk or cloud run artifacts) before finishing."""
    from _shared.validate_sql_artifacts import validate_sql_dir

    ctx = _run_context
    run_id = resolve_run_id(ctx) if ctx else None

    # Cloud pipeline: SQL lives in S3 under runs/<runId>/<slug>/db/sql/ — not on
    # the AgentCore container disk. Materialize only those files for validation.
    if _is_cloud_store() and run_id:
        try:
            with _cloud_sql_dir_for_validation(service, run_id) as sql_dir:
                return _format_sql_validation_result(validate_sql_dir(sql_dir))
        except FileNotFoundError as exc:
            return f"Error: {exc}"
        except Exception as exc:
            return f"Error: failed to load SQL artifacts for validation: {exc}"

    sql_dir = _service_dir(service) / "db" / "sql"
    if not sql_dir.is_dir():
        return f"Error: no sql directory at {sql_dir.relative_to(_REPO_ROOT).as_posix()}"
    return _format_sql_validation_result(validate_sql_dir(sql_dir))


def _enrich_postgres_mcp_context(ctx: dict[str, Any], *, use_postgres: bool) -> None:
    """Inject RDS target and post-run apply flag when --with-postgres is set."""
    ctx.setdefault("seedMinRows", int(_SEED_MIN_ROWS))
    ctx.setdefault("seedMaxRows", int(_SEED_MAX_ROWS))
    if not use_postgres:
        return
    params = postgres_mcp_tool_params()
    ctx["postgresMcpParams"] = params
    ctx["postgresAppSchema"] = (ctx.get("targetApp") or "").replace("-", "_")
    ctx["applyToRdsAfterWrite"] = True
    warnings: list[str] = []
    if not params.get("db_endpoint"):
        warnings.append("POSTGRES_MCP_DB_ENDPOINT is not set.")
    if not params.get("database"):
        warnings.append("POSTGRES_MCP_DATABASE is not set.")
    if warnings:
        ctx["postgresMcpWarning"] = " ".join(warnings) + " RDS apply will fail until env is configured."


def _apply_sql_verbose() -> bool:
    return os.getenv("DATABASE_AGENT_VERBOSE", os.getenv("APPLY_SQL_VERBOSE", "")).strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _strip_agent_files_written_section(text: str) -> str:
    """Remove duplicate file list if the model still emitted ## Files written."""
    return re.sub(r"\n## Files written\r?\n.*", "", text, flags=re.DOTALL).strip()


def _apply_sql_to_rds(target_app: str) -> int:
    """Apply sql/ to RDS via scripts/apply_sql_to_rds.py (psycopg, no Bedrock)."""
    import subprocess

    from _shared.validate_sql_artifacts import validate_sql_dir

    sql_dir = _service_dir(target_app) / "db" / "sql"
    pre_errors = validate_sql_dir(sql_dir) if sql_dir.is_dir() else []
    if pre_errors:
        print("[database-agent] SQL validation failed before RDS apply:", file=sys.stderr)
        for err in pre_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    script = _REPO_ROOT / "scripts" / "apply_sql_to_rds.py"
    # --reset-schema: a fresh pipeline run must drop+recreate the app schema so a
    # seed INSERT never hits a stale table with mismatched columns (e.g. leftover
    # columns from a previous run's schema). Safe on dev/seed RDS; the later
    # explicit apply step in run-sdlc-local.ps1 already does this too.
    cmd = [sys.executable, str(script), "--target-app", target_app, "--reset-schema"]
    if not _apply_sql_verbose():
        cmd.append("--quiet")
    print(f"[database-agent] Applying sql/ to RDS ({target_app})...", file=sys.stderr)
    return subprocess.call(cmd, cwd=_REPO_ROOT)


def _max_output_tokens() -> int:
    """Bedrock output cap; 8k truncates multi-file migrations + seed in one run."""
    return int(
        os.getenv(
            "DATABASE_AGENT_MAX_TOKENS",
            os.getenv("BEDROCK_MAX_OUTPUT_TOKENS", "32768"),
        )
    )


def _model_id(ctx: dict[str, Any] | None = None) -> str:
    """Same MODEL_ID as Claude Sonnet 4.6; pipeline retries pass modelOverride (Haiku fallback)."""
    if ctx:
        override = str(ctx.get("modelOverride") or "").strip()
        if override:
            return override
    return os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-6").strip()


def _coding_model(ctx: dict[str, Any] | None = None) -> BedrockModel:
    model_id = _model_id(ctx)
    read_timeout = int(os.getenv("BEDROCK_READ_TIMEOUT", "600"))
    max_tokens = _max_output_tokens()
    return BedrockModel(
        model_id=model_id,
        region_name=os.getenv("AWS_REGION", "us-east-2"),
        streaming=True,
        max_tokens=max_tokens,
        cache_config=CacheConfig(strategy="auto"),
        cache_tools="default",
        boto_client_config=botocore.config.Config(
            read_timeout=read_timeout,
            connect_timeout=10,
            retries={"mode": "standard", "max_attempts": 2},
        ),
    )


def _build_context(
    *,
    target_app: str,
    db_subdir: str = _DEFAULT_DB_SUBDIR,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    slug = slugify(target_app)
    root_rel = target_app_root_rel(slug)
    if not _is_cloud_store():
        service_dir = _ensure_service_exists(target_app)
        (service_dir / db_subdir).mkdir(parents=True, exist_ok=True)
    ctx: dict[str, Any] = {
        "targetApp": slug,
        "targetAppDir": root_rel,
        "dbOutputDir": f"{root_rel}/{db_subdir}".rstrip("/"),
        "preferredSqlPath": f"{root_rel}/{db_subdir}/sql".replace("//", "/"),
        "preferredNoSqlPath": f"{root_rel}/{db_subdir}/nosql".replace("//", "/"),
    }
    if extra:
        ctx.update(extra)
    return ctx


def _clear_sql_output_dir(target_app: str, db_subdir: str = _DEFAULT_DB_SUBDIR) -> None:
    """Empty target-apps/<app>/<db_subdir>/sql/ before the agent regenerates it.

    Database-agent always rewrites the complete migration set from the design doc
    each run — it never reads old sql/ files as input (see DEFAULT_PIPELINE_TASK) —
    so clearing first is safe. This removes the class of bug where an earlier run's
    differently-named file for the same migration (e.g. 001_zones.sql) survives
    alongside the new run's file (001_create_zones.sql): the agent's tool set has
    no delete capability, so previously it could only stub old files with a
    "-- Superseded by ..." comment, never actually remove them.

    Cloud/S3 mode (ARTIFACT_STORE=s3) is skipped deliberately, not just as cheap
    insurance: write_repo_artifact keys every write under runs/<runId>/... (a fresh
    UUID minted per pipeline run — see artifact_store.new_run_id/resolve_run_id), so
    an old run's files live under an entirely different S3 prefix and can never
    coexist with a new run's files for the same app. The only way this could recur
    in cloud mode is an explicit resume that reuses the SAME runId across separate
    database-agent invocations — a narrow, deliberate case distinct from normal
    regeneration, and out of scope for this fix.
    """
    if _is_cloud_store():
        return
    sql_dir = _service_dir(target_app) / db_subdir / "sql"
    if not sql_dir.is_dir():
        return
    removed = list(sql_dir.glob("*.sql"))
    for path in removed:
        path.unlink()
    if removed:
        print(f"[database-agent] cleared {len(removed)} stale sql files", file=sys.stderr)

def _load_database_schema_handoff_block(context: dict[str, Any]) -> str:
    """Validated structured DB contract from architect-agent, if present - see handoff_schemas.py.

    Best-effort: absent on older runs or when architect-agent's generation failed, in which case
    this returns "" and the agent falls back to designDocPath §3/§6 exactly as it always has.
    """
    rel = str(context.get("dbSchemaHandoffPath") or "").strip()
    if not rel:
        return ""
    try:
        from _shared.handoff_schemas import DatabaseHandoff, load_handoff_artifact

        handoff = load_handoff_artifact(rel, DatabaseHandoff, context=context)
    except Exception as exc:  # noqa: BLE001 - validation/read failure must not block the run
        print(f"[{AGENT_NAME}] dbSchemaHandoffPath present but unusable, falling back to design sections 3/6: {exc}")
        return ""
    return (
        "\n\n## Database contract (validated, from architect-agent - use this for table/column/"
        "index/FK detail; design §3/§6 remain the source for anything not covered here)\n"
        f"{handoff.model_dump_json(indent=2, exclude_none=True)}\n"
    )



def _user_message(task: str, context: dict[str, Any] | None) -> str:
    if not context:
        return task
    handoff_block = _load_database_schema_handoff_block(context)
    return f"{task}{handoff_block}\n\nContext:\n{json.dumps(context, indent=2)}"


def _build_agent(
    tools: list[Any],
    ctx: dict[str, Any] | None = None,
    *,
    telemetry: RunTelemetry | None = None,
) -> Agent:
    callback = (
        StrandsTelemetryCallback(AGENT_NAME, telemetry)
        if telemetry is not None
        else None
    )
    return Agent(
        agent_id=AGENT_NAME,
        name=AGENT_NAME,
        description="Designs SQL/NoSQL schemas, migrations, and DB execution plans for target apps.",
        model=_coding_model(ctx),
        system_prompt=_build_system_prompt(ctx),
        tools=tools,
        callback_handler=callback,
    )


def _file_tools() -> list[Any]:
    return [db_list_tree, db_read_file, db_write_file, db_delete_file, db_validate_sql]


def _mongodb_mcp_tools(stack: ExitStack) -> list[Any]:
    """Attach MongoDB MCP tools when design requires document storage."""
    client = stack.enter_context(mongodb_mcp_client(cwd=_REPO_ROOT))
    return client.list_tools_sync()


def _build_toolset(
    stack: ExitStack,
    *,
    use_mongodb: bool = False,
) -> list[Any]:
    """File tools plus optional MongoDB MCP. RDS apply is post-run via apply_sql_to_rds.py."""
    tools = _file_tools()
    if use_mongodb:
        tools.extend(_mongodb_mcp_tools(stack))
    return tools


def run_task(
    task: str,
    context: dict[str, Any] | None = None,
    *,
    target_app: str | None = None,
    db_subdir: str = _DEFAULT_DB_SUBDIR,
    use_postgres: bool = False,
    use_mongodb: bool = False,
) -> tuple[str, list[str]]:
    global _written_files, _deleted_files, _run_context
    _written_files = []
    _deleted_files = []
    _run_context = None

    app = resolve_target_app(target_app, context, env_var="DATABASE_TARGET_APP")
    base_ctx = dict(context) if context is not None else {}
    base_ctx.setdefault("targetApp", app)
    ctx = merge_run_handoff_context(base_ctx, include_db_paths=False)
    for key, value in _build_context(target_app=app, db_subdir=db_subdir).items():
        if _is_cloud_store() or key not in ctx:
            ctx[key] = value
    _enrich_postgres_mcp_context(ctx, use_postgres=use_postgres)
    _run_context = ctx

    try:
        with ExitStack() as stack:
            toolset = _build_toolset(stack, use_mongodb=use_mongodb)
            telemetry = RunTelemetry(
                AGENT_NAME,
                target_app=app,
                model_id=_model_id(ctx),
                run_id=str(ctx.get("runId") or ctx.get("run_id") or "").strip() or None,
            )
            agent = _build_agent(toolset, ctx, telemetry=telemetry)
            summary = str(agent(_user_message(task, ctx)))
    except MCPClientInitializationError as exc:
        raise SystemExit(
            "MongoDB MCP failed to start.\n"
            "Check MDB_MCP_* env and MCP server install.\n"
            f"Details: {exc}"
        ) from exc
    finally:
        _run_context = None

    if not _written_files:
        summary += (
            "\n\n> No files were written under target-apps/. "
            "Use db_write_file to persist SQL/NoSQL scripts.\n"
        )
    telemetry.extra = {"filesWritten": len(_written_files), "filesDeleted": len(_deleted_files)}
    telemetry.finalize(context=ctx)

    run_id = resolve_run_id(ctx)
    if run_id:
        ctx.setdefault("runId", run_id)
        put_context(run_id, ctx)
        if _written_files:
            handoff_rel = write_db_handoff(
                app,
                ctx,
                agent_result=summary,
                rds_applied=False,
            )
            ctx["databaseHandoffPath"] = handoff_rel
            put_context(run_id, ctx)

    return summary, list(_written_files)


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


def _execute_database_pipeline_message(
    message: Any,
    *,
    use_postgres: bool = False,
    use_mongodb: bool = False,
) -> str:
    """AgentCore A2A: parse Context, run_task (sets _run_context for S3 writes)."""
    text = _prompt_to_text(message)
    from _shared.control_plane_health import is_control_plane_health_check

    if is_control_plane_health_check(text):
        return "OK"
    task, ctx = parse_task_and_context(text)
    if not task.strip():
        task = DEFAULT_PIPELINE_TASK
    try:
        summary, written = run_task(
            task,
            ctx or None,
            use_postgres=use_postgres,
            use_mongodb=use_mongodb,
        )
    except (ValueError, TargetAppRequiredError, SystemExit) as exc:
        return _database_pipeline_error_message(exc, ctx)
    except Exception as exc:
        return _database_pipeline_error_message(exc, ctx)

    lines = [summary]
    if written:
        lines.append(f"\nPersisted {len(written)} file(s) to artifact store:")
        for path in written:
            lines.append(f"  - {path}")
    run_id = resolve_run_id(ctx)
    if run_id:
        lines.append(f"- runId: {run_id}")
        if is_s3_store():
            lines.append(f"- s3Prefix: runs/{run_id}/")
    return "\n".join(lines)


def _database_pipeline_error_message(exc: BaseException, ctx: dict[str, Any]) -> str:
    run_id = resolve_run_id(ctx) or "smoke-001"
    app = (ctx or {}).get("targetApp") or "inventory-app"
    root = target_app_root_rel(app)
    example = {
        "targetApp": app,
        "runId": run_id,
        "designDocPath": f"{root}/docs/design/{app}.md",
        "prdPath": f"{root}/docs/PRD/{app}.md",
        "dbOutputDir": f"{root}/db",
        "preferredSqlPath": f"{root}/db/sql",
    }
    hint = ""
    msg = str(exc)
    if "ARTIFACT_S3_BUCKET" in msg:
        hint = (
            "\n\nRuntime env: set ARTIFACT_STORE=s3 and ARTIFACT_S3_BUCKET on the "
            "database_agent AgentCore deploy (see scripts/deploy-agentcore-agents.ps1)."
        )
    elif "AccessDenied" in msg or "403" in msg:
        hint = (
            "\n\nIAM: AgentCore execution role needs s3:GetObject and s3:PutObject on "
            f"s3://<ARTIFACT_S3_BUCKET>/runs/*."
        )
    return (
        "Database pipeline could not start.\n\n"
        f"Reason: {type(exc).__name__}: {exc}{hint}\n\n"
        "Ensure product + architect ran first and S3 has PRD/design under runs/<runId>/:\n\n"
        f"Context:\n{json.dumps(example, indent=2)}\n"
    )


def _agent_result_from_text(text: str) -> Any:
    from strands.agent.agent_result import AgentResult
    from strands.telemetry.metrics import EventLoopMetrics

    return AgentResult(
        stop_reason="end_turn",
        message={"role": "assistant", "content": [{"text": text}]},
        metrics=EventLoopMetrics(),
        state={},
    )


def build_database_pipeline_agent(
    tools: list[Any],
    *,
    use_postgres: bool = False,
    use_mongodb: bool = False,
) -> Agent:
    """AgentCore mode: run_task on each A2A message so db_write_file uploads to S3."""
    agent = _build_agent(tools)

    def database_invoke(message: Any, **kwargs: Any) -> str:
        del kwargs
        return _execute_database_pipeline_message(
            message,
            use_postgres=use_postgres,
            use_mongodb=use_mongodb,
        )

    async def database_stream_async(
        prompt: Any = None,
        *,
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        from strands.types._events import AgentResultEvent

        del invocation_state, kwargs
        try:
            summary = _execute_database_pipeline_message(
                prompt,
                use_postgres=use_postgres,
                use_mongodb=use_mongodb,
            )
        except Exception as exc:
            _, ctx = parse_task_and_context(_prompt_to_text(prompt))
            summary = _database_pipeline_error_message(exc, ctx)
        yield AgentResultEvent(result=_agent_result_from_text(summary)).as_dict()

    agent.__call__ = database_invoke  # type: ignore[method-assign]
    agent.stream_async = database_stream_async  # type: ignore[method-assign]
    return agent


def serve_a2a(
    host: str = "127.0.0.1",
    port: int = A2A_PORT,
    *,
    use_mongodb: bool = False,
) -> None:
    skills = [
        AgentSkill(
            id="database_design_and_scripts",
            name="database_design_and_scripts",
            description="Create SQL/NoSQL schema artifacts, migrations, and DB command playbooks.",
            tags=["database", "postgres", "mongodb", "schema", "migration"],
        )
    ]
    with ExitStack() as stack:
        tools = _build_toolset(stack, use_mongodb=use_mongodb)
        agent = _build_agent(tools)
        A2AServer(agent, host=host, port=port, skills=skills).serve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Database agent - Strands + optional MongoDB MCP; RDS via host script")
    parser.add_argument(
        "--task",
        help="Optional override. Default: pipeline task (reads design/PRD from Context).",
    )
    parser.add_argument(
        "--target-app",
        help="Service folder under target-apps/ (from --target-app, context targetApp, or PIPELINE_TARGET_APP)",
    )
    parser.add_argument(
        "--db-subdir",
        default=_DEFAULT_DB_SUBDIR,
        help=f"DB artifacts folder under target app (default: {_DEFAULT_DB_SUBDIR})",
    )
    parser.add_argument(
        "--no-auto-context",
        action="store_true",
        help="Do not load agents/pipeline/<target-app>.context.json when --context-file/json omitted",
    )
    load_context_extra(parser)

    mcp = parser.add_argument_group("MCP backends (default is file tools only; flags compose)")
    mcp.add_argument(
        "--with-postgres",
        action="store_true",
        help="Generate sql/ with Bedrock, then apply to RDS via apply_sql_to_rds.py (no Bedrock on apply).",
    )
    mcp.add_argument(
        "--apply-sql-only",
        action="store_true",
        help="Skip Bedrock; only apply existing target-apps/<app>/db/sql/*.sql to RDS.",
    )
    mcp.add_argument(
        "--with-mongodb",
        action="store_true",
        help="Attach MongoDB MCP — apply nosql/ scripts (combine with --with-postgres when design needs both)",
    )
    parser.add_argument(
        "--full-regen",
        action="store_true",
        help=(
            "Set only by the orchestrator: this is a full from-scratch regeneration, "
            "so skip self-apply here — the orchestrator's own dedicated rds-apply step "
            "(which resets the schema first) is the sole apply for this run. Standalone "
            "CLI use should never pass this — self-apply is the only apply mechanism there."
        ),
    )
    parser.add_argument("--serve-a2a", action="store_true", help=f"Start A2A server on :{A2A_PORT}")
    parser.add_argument("--port", type=int, default=A2A_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    use_postgres = args.with_postgres
    use_mongodb = args.with_mongodb

    if args.serve_a2a:
        serve_a2a(host=args.host, port=args.port, use_mongodb=use_mongodb)
        return

    try:
        extra, app = resolve_cli_context(
            args.target_app,
            parse_context_args(args),
            no_auto_context=args.no_auto_context,
            env_var="DATABASE_TARGET_APP",
        )
    except TargetAppRequiredError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if args.apply_sql_only:
        context = _build_context(target_app=app, db_subdir=args.db_subdir, extra=extra or None)
        enrich_handoff_context(context)
        _enrich_postgres_mcp_context(context, use_postgres=True)
        apply_code = _apply_sql_to_rds(app)
        handoff_rel = write_db_handoff(
            app, context, rds_applied=apply_code == 0,
        )
        print(f"[database-agent] Handoff file  : {handoff_rel}", file=sys.stderr)
        raise SystemExit(apply_code)

    if not args.task and not args.serve_a2a:
        args.task = DEFAULT_PIPELINE_TASK

    context = _build_context(target_app=app, db_subdir=args.db_subdir, extra=extra or None)
    enrich_handoff_context(context)
    _enrich_postgres_mcp_context(context, use_postgres=use_postgres)

    _clear_sql_output_dir(app, args.db_subdir)

    task = args.task or DEFAULT_PIPELINE_TASK

    model_id = _model_id(context)
    print(f"[database-agent] Model: {model_id}", file=sys.stderr)
    if use_postgres:
        params = context.get("postgresMcpParams") or {}
        print(
            f"[database-agent] RDS: {params.get('db_endpoint', '(POSTGRES_MCP_DB_ENDPOINT not set)')}"
            f" / {params.get('database', '(not set)')}",
            file=sys.stderr,
        )
        if context.get("postgresMcpWarning"):
            print(f"[database-agent] WARNING: {context['postgresMcpWarning']}", file=sys.stderr)
    print("[database-agent] Running...", file=sys.stderr)

    result, written = run_task(
        task,
        context,
        target_app=app,
        db_subdir=args.db_subdir,
        use_postgres=use_postgres,
        use_mongodb=use_mongodb,
    )
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(_strip_agent_files_written_section(result))
    if written:
        print(f"[database-agent] Wrote {len(written)} file(s):", file=sys.stderr)
        for path in written:
            print(f"  {path}", file=sys.stderr)
    else:
        print("[database-agent] No files written under target-apps/.", file=sys.stderr)

    rds_applied = False
    if use_postgres and args.full_regen:
        print(
            "[database-agent] --full-regen: skipping self-apply — the orchestrator's "
            "dedicated rds-apply step (schema reset first) owns this run's apply.",
            file=sys.stderr,
        )
    elif use_postgres:
        apply_code = _apply_sql_to_rds(app)
        if apply_code != 0:
            handoff_rel = write_db_handoff(
                app,
                context,
                agent_result=result,
                rds_applied=False,
            )
            print(f"[database-agent] Handoff file  : {handoff_rel}", file=sys.stderr)
            print(
                "[database-agent] SQL files are on disk; RDS apply failed — see FAILED line above. "
                "Retry: python scripts/apply_sql_to_rds.py "
                f"--target-app {app} --verbose",
                file=sys.stderr,
            )
            raise SystemExit(apply_code)
        print("[database-agent] RDS apply finished.", file=sys.stderr)
        rds_applied = True

    handoff_rel = write_db_handoff(
        app,
        context,
        agent_result=result,
        rds_applied=rds_applied,
    )
    print(f"[database-agent] Handoff file  : {handoff_rel}", file=sys.stderr)


if __name__ == "__main__":
    main()