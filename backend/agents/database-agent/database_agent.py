"""Database agent - Strands + Bedrock + Postgres & MongoDB MCP Servers"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TARGET_APPS = _REPO_ROOT / "target-apps"
_DEFAULT_DB_SUBDIR = "db"

sys.path.insert(0, str(_REPO_ROOT / "agents"))
from _shared.context_cli import load_context_extra, parse_context_args
from _shared.db_handoff import write_db_handoff
from _shared.env import load_repo_env
from _shared.mcp_clients import mongodb_mcp_client, postgres_mcp_client, postgres_mcp_tool_params
from _shared.runner import coding_model_id
from _shared.pipeline_context import (
    TargetAppRequiredError,
    enrich_handoff_context,
    resolve_cli_context,
    resolve_target_app,
    slugify,
)
from _shared.telemetry import RunTelemetry, StrandsTelemetryCallback

load_repo_env()

import botocore.config
from a2a.types import AgentSkill
from strands import Agent
from strands.models import BedrockModel
from strands.models.model import CacheConfig
from strands.multiagent.a2a import A2AServer
from strands.tools.decorator import tool
from strands.types.exceptions import MCPClientInitializationError

AGENT_NAME = "database-agent"
A2A_PORT = 9108

_SEED_MIN_ROWS = os.getenv("SEED_MIN_ROWS", "5")
_SEED_MAX_ROWS = os.getenv("SEED_MAX_ROWS", "10")

# Used when --task is omitted: agent reads design/PRD from Context, not from the CLI string.
DEFAULT_PIPELINE_TASK = """\
Implement the database layer as a DB developer using Context handoff.
1. db_read_file(designDocPath) — §3 (tables) and §6 (migration order + seed).
2. If prdPath is in Context, db_read_file(prdPath) — validate every RDS table maps to PRD §7 or design §3; skip entities that live in Athena/S3/Jira only.
3. db_list_tree dbOutputDir; db_write_file idempotent scripts under preferredSqlPath (and nosql/ only if design requires MongoDB).
4. When `applyToRdsAfterWrite` is true in Context: write sql/ only — the host applies files to RDS after this run (do not call postgres_run_query).
   MongoDB MCP (if present): apply nosql/ scripts when design requires document storage.
5. Call `db_validate_sql(service=targetApp)` after writing sql/ — fix every SQL_VALIDATION FAILED before finishing.
6. Reply once: schema_summary, sql_artifacts, handoff_for_developer. Omit execution_commands when applyToRdsAfterWrite is true.
   The host writes `db/HANDOFF.md` after the run — do not db_write_file HANDOFF.md yourself.\
"""

_READ_PREFIXES = (
    _TARGET_APPS,
    _REPO_ROOT / "docs",
    _REPO_ROOT / "agents",
    _REPO_ROOT / "inputs",
)

_written_files: list[str] = []

DATABASE_SYS_PROMPT = """\
You are the **database developer** for the Autonomous SDLC platform. You run after architect-agent
and before developer-agent. You author migrations and dev seeds; the host applies sql/ to RDS when requested.

## Handoff (read files — not prior agent chat)
| Source | Action | Use |
|--------|--------|-----|
| `designDocPath` | `db_read_file` | **§3** → DDL; **§6** → file order + seed spec |
| `prdPath` | `db_read_file` when present | PRD **§7 Core Data Entities** — validate RDS scope |
| `productAgentOutput` | Context JSON | Orientation only |
| `diagramPaths` | Context JSON | Optional; do not parse PNGs |
| `postgresMcpParams` | Context JSON (when `--with-postgres`) | RDS target (endpoint, database) for handoff only |
| `applyToRdsAfterWrite` | Context JSON | When true, write sql/ only; host runs apply script after agent completes |
| `seedMinRows` / `seedMaxRows` | Context JSON | Dev seed row targets per RDS table (see Artifacts) |

## PRD / design scope (required before any DDL)
1. Create **only** tables listed in design **§3** (architect already trimmed to PRD).
2. Cross-check `prdPath` §7: include a table only if the app must **persist** that entity in Postgres/MongoDB.
3. **Do not** add RDS tables for:
   - **Cost Record** / CUR line items → Athena + S3 (query at runtime, not migrated here)
   - **External Jira ticket body** → Jira API; app stores link rows only
   - **Executive summary files** → S3; `executive_summaries` holds keys/metadata only
4. **`jira_tickets` (FR-6):** required when design §3 lists it — stores `recommendation_id`, `jira_key`, `jira_url`
   after approve. This is the app's foreign link to Jira, not a duplicate of Jira's database.
5. Do not invent tables, columns, or migrations absent from design §3/§6.

## Artifacts
Under `dbOutputDir` (default `target-apps/<service>/db/`):
- `HANDOFF.md` — host-written after each CLI run (developer-agent reads `databaseHandoffPath`)
- `sql/001_*.sql` … numbered, idempotent DDL (`IF NOT EXISTS` where possible)
- **Postgres extensions before indexes:** `CREATE EXTENSION IF NOT EXISTS pg_trgm` (and any other extension) must run in an early migration **before** any index using `gin_trgm_ops` or extension-specific operator classes — never only in seed files.
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
  - **`api_keys.key_hash` UNIQUE:** never insert multiple rows with the same `__BCRYPT_PLACEHOLDER__` — use one row per tier or pre-hash distinct API key strings; placeholders are for `users` password columns only.
- `sql/*_seed.sql` or `011_seed.sql` — **dev/test fixture rows only** per design §6.2 (not production CUR data).
  Use `seedMinRows`–`seedMaxRows` from Context: **every RDS table in §3 must get that many INSERT rows**
  (realistic names/emails/dates; stable UUIDs only where tests need them; respect FK order; `ON CONFLICT DO NOTHING`).
  Do not leave any §3 table empty in seed unless design §6.2 explicitly excludes it.
- **Optional / nullable columns:** When design §3 marks a field optional (e.g. `ends_at`, `description`)
  or seed uses `NULL` for it, DDL must **omit** `NOT NULL`. Call `db_validate_sql` before finishing —
  it blocks NULL inserts into NOT NULL columns. `CREATE TABLE IF NOT EXISTS` does not change nullability
  on existing RDS tables; the host apply script reconciles drift, but your schema files must match design.
- **JWT seed users:** use `__BCRYPT_PLACEHOLDER__` in the password hash column — use the **exact column name from your DDL** (`hashed_password`, `password_hash`, `password`, etc.). See **Seeding credentials** below for the three mandatory steps. Never invent `$2b$12$...` strings.
- `nosql/` — **only** when design §3/§6 explicitly requires MongoDB collections

## RDS apply (host — not your job when `applyToRdsAfterWrite` is true)
- **Do not** use `postgres_run_query` to apply migrations. The CLI runs `scripts/apply_sql_to_rds.py` after you finish.
- Write complete, idempotent `sql/` files in §6 order; host applies them to RDS.

## MongoDB MCP (only when attached)
- Apply scripts under `nosql/` when design requires document storage.

## Workflow
1. Read design (+ PRD when `prdPath` set); list planned tables with PRD FR ids.
2. `db_list_tree` / overwrite stale files via `db_write_file`; **delete** superseded `sql/` files (do not leave duplicate `00N_*.sql` no-ops).
3. Write migrations in §6 order; write seed with `seedMinRows`–`seedMaxRows` rows per §3 table.
4. `db_validate_sql(service=targetApp)` — must report SQL_VALIDATION OK.
5. One compact reply (see below).

## Response format (single pass — no duplication)
Return **once**, in order:
1. **schema_summary** — table/collection count, enums, PRD FR mapping (≤12 bullets)
2. **sql_artifacts** — ordered paths only (table, no prose repeat)
3. **handoff_for_developer** — DSN pattern, SQLAlchemy/ORM notes, stable seed UUIDs if any (≤8 bullets)
4. **execution_commands** — **omit** when `applyToRdsAfterWrite` is true; include **only** for files-only runs (short apply note, not a full bash essay)

Do **not** repeat sections. Do **not** paste full SQL bodies in the reply.
Do **not** add a `## Files written` section — the CLI logs written paths on stderr.
Use **one `db_write_file` call per sql file**; put full SQL only in the tool `content` argument, not in chat text.

## Guardrails
- Never write outside `target-apps/`.
- Do not modify `docs/design/*.md`, PRD, or secrets.
- No password literals in SQL files.

## Seeding credentials — DO NOT invent hashes

When any seed row has a password hash column (`hashed_password`, `password_hash`, `password`, etc.), **NEVER write a literal bcrypt/argon/scrypt string**. The LLM cannot compute real hashes; any `$2b$12$...` string you produce will be random characters that fail every `bcrypt.checkpw(...)` call and break login.

### All three steps are MANDATORY — skipping any one causes silent 401 on RDS

**Step 1 — Sentinel value in every seed user row**
Insert `'__BCRYPT_PLACEHOLDER__'` in the hash column. Use the **exact column name from your DDL** — never assume `password_hash`; read the `CREATE TABLE` you just wrote.

```sql
INSERT INTO users (id, username, hashed_password, role) VALUES
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

**Step 3 — Credential map in `HANDOFF.md` under `### seedCredentials` (MANDATORY)**
```
### seedCredentials
| username | role      | plaintext_password |
|----------|-----------|--------------------|
| alice    | admin     | YourPassword123!   |
| bob      | viewer    | YourPassword123!   |
```
- First column: the login field value (`username` value or `email` value — whichever the app uses to log in)
- Third column: the plaintext password (must match the SQL comment exactly)
- Use `email` values in column 1 when the users table has an `email` login column (no `username`)

The host pipeline runs `agents/_shared/materialize_seed_passwords.py` after RDS apply — it reads **Step 2** for the password, then **Step 3** and/or parses `INSERT INTO users (...)` column order from seed SQL to find which rows to update, then UPDATEs the hash column with a real bcrypt hash computed on CPU.

If users table uses `email` as the login column (no `username`), list emails in `### seedCredentials` and ensure the seed `INSERT` column list includes `email` and the hash column name from your DDL.

Same rule for `api_key_hash`, `verification_token`, or any column storing a hash-of-known-plaintext. Sentinel + SQL comment + HANDOFF.md map — all three, every time.
"""


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
        if not str(candidate).startswith(str(_TARGET_APPS.resolve())):
            raise ValueError("writes only allowed under target-apps/")
        return candidate
    allowed = any(str(candidate).startswith(str(prefix.resolve())) for prefix in _READ_PREFIXES)
    if not allowed:
        raise ValueError(f"read not allowed for path: {relative_path}")
    return candidate


@tool
def db_list_tree(service: str, subpath: str = "") -> str:
    """List files under target-apps/<service>/ (optionally under subpath)."""
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
    """Write a file under target-apps/ only."""
    try:
        file_path = _resolve_repo_path(path, write=True)
    except ValueError as exc:
        return f"Error: {exc}"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8", newline="\n")
    rel = file_path.relative_to(_REPO_ROOT).as_posix()
    _written_files.append(rel)
    return f"Wrote {rel} ({len(content)} bytes)"


@tool
def db_validate_sql(service: str) -> str:
    """Validate db/sql/ schema vs seed nullability (blocks NULL inserts into NOT NULL columns)."""
    from _shared.validate_sql_artifacts import validate_sql_dir

    sql_dir = _service_dir(service) / "db" / "sql"
    if not sql_dir.is_dir():
        return f"Error: no sql directory at {sql_dir.relative_to(_REPO_ROOT).as_posix()}"
    errors = validate_sql_dir(sql_dir)
    if not errors:
        return "SQL_VALIDATION OK — schema and seed nullability are consistent."
    lines = "\n".join(f"  - {e}" for e in errors)
    return (
        "SQL_VALIDATION FAILED — fix schema or seed before RDS apply:\n"
        f"{lines}\n"
        "Rule: optional columns omit NOT NULL in DDL; seed NULL only for nullable columns."
    )


@tool
def db_get_postgres_params() -> str:
    """Return JSON connection params for postgres_run_query (from POSTGRES_MCP_* env)."""
    return json.dumps(postgres_mcp_tool_params(), indent=2)


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
    cmd = [sys.executable, str(script), "--target-app", target_app]
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


def _coding_model() -> BedrockModel:
    model_id = coding_model_id()
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
    service_dir = _ensure_service_exists(target_app)
    db_dir = service_dir / db_subdir
    db_dir.mkdir(parents=True, exist_ok=True)
    ctx: dict[str, Any] = {
        "targetApp": target_app,
        "targetAppDir": service_dir.relative_to(_REPO_ROOT).as_posix(),
        "dbOutputDir": db_dir.relative_to(_REPO_ROOT).as_posix(),
        "preferredSqlPath": (db_dir / "sql").relative_to(_REPO_ROOT).as_posix(),
        "preferredNoSqlPath": (db_dir / "nosql").relative_to(_REPO_ROOT).as_posix(),
    }
    if extra:
        ctx.update(extra)
    return ctx


def _user_message(task: str, context: dict[str, Any] | None) -> str:
    if not context:
        return task
    return f"{task}\n\nContext:\n{json.dumps(context, indent=2)}"


def _build_agent(tools: list[Any], *, telemetry: RunTelemetry | None = None) -> Agent:
    callback = (
        StrandsTelemetryCallback(AGENT_NAME, telemetry)
        if telemetry is not None
        else None
    )
    return Agent(
        agent_id=AGENT_NAME,
        name=AGENT_NAME,
        description="Designs SQL/NoSQL schemas, migrations, and DB execution plans for target apps.",
        model=_coding_model(),
        system_prompt=DATABASE_SYS_PROMPT,
        tools=tools,
        callback_handler=callback,
    )


def _file_tools() -> list[Any]:
    return [db_list_tree, db_read_file, db_write_file, db_validate_sql]


def _postgres_mcp_tools(stack: ExitStack) -> list[Any]:
    """Attach AWS Postgres MCP tools (composable with MongoDB MCP)."""
    client = stack.enter_context(postgres_mcp_client(cwd=_REPO_ROOT))
    return client.list_tools_sync()


def _mongodb_mcp_tools(stack: ExitStack) -> list[Any]:
    """Attach MongoDB MCP tools (composable with Postgres MCP)."""
    client = stack.enter_context(mongodb_mcp_client(cwd=_REPO_ROOT))
    return client.list_tools_sync()


def _build_toolset(
    stack: ExitStack,
    *,
    use_postgres: bool = False,
    use_mongodb: bool = False,
) -> list[Any]:
    """File tools plus MongoDB MCP when requested. Postgres RDS apply is post-run, not MCP."""
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
    global _written_files
    _written_files = []

    app = resolve_target_app(target_app, context, env_var="DATABASE_TARGET_APP")
    ctx = context if context is not None else _build_context(target_app=app, db_subdir=db_subdir)
    ctx.setdefault("targetApp", app)
    service_dir = _ensure_service_exists(app)
    ctx.setdefault("targetAppDir", service_dir.relative_to(_REPO_ROOT).as_posix())
    db_dir = service_dir / db_subdir
    db_dir.mkdir(parents=True, exist_ok=True)
    ctx.setdefault("dbOutputDir", db_dir.relative_to(_REPO_ROOT).as_posix())
    ctx.setdefault("preferredSqlPath", (db_dir / "sql").relative_to(_REPO_ROOT).as_posix())
    ctx.setdefault("preferredNoSqlPath", (db_dir / "nosql").relative_to(_REPO_ROOT).as_posix())
    enrich_handoff_context(ctx)
    _enrich_postgres_mcp_context(ctx, use_postgres=use_postgres)

    try:
        with ExitStack() as stack:
            toolset = _build_toolset(stack, use_postgres=use_postgres, use_mongodb=use_mongodb)
            telemetry = RunTelemetry(AGENT_NAME, target_app=app, model_id=coding_model_id())
            agent = _build_agent(toolset, telemetry=telemetry)
            summary = str(agent(_user_message(task, ctx)))
    except MCPClientInitializationError as exc:
        backends = []
        if use_postgres:
            backends.append("Postgres")
        if use_mongodb:
            backends.append("MongoDB")
        label = " + ".join(backends) if backends else "MCP"
        raise SystemExit(
            f"{label} MCP failed to start.\n"
            "Check POSTGRES_MCP_* / MDB_MCP_* env and MCP server install.\n"
            f"Details: {exc}"
        ) from exc

    if not _written_files:
        summary += (
            "\n\n> No files were written under target-apps/. "
            "Use db_write_file to persist SQL/NoSQL scripts.\n"
        )
    telemetry.extra = {"filesWritten": len(_written_files)}
    telemetry.finalize()
    return summary, list(_written_files)


def run_task_files_only(
    task: str,
    context: dict[str, Any] | None = None,
    *,
    target_app: str | None = None,
    db_subdir: str = _DEFAULT_DB_SUBDIR,
) -> tuple[str, list[str]]:
    """Write/read SQL files only — no Postgres or MongoDB MCP processes."""
    return run_task(
        task,
        context,
        target_app=target_app,
        db_subdir=db_subdir,
        use_postgres=False,
        use_mongodb=False,
    )


def run_task_with_postgres(
    task: str,
    context: dict[str, Any] | None = None,
    *,
    target_app: str | None = None,
    db_subdir: str = _DEFAULT_DB_SUBDIR,
) -> tuple[str, list[str]]:
    """File tools + AWS Postgres MCP."""
    return run_task(
        task,
        context,
        target_app=target_app,
        db_subdir=db_subdir,
        use_postgres=True,
        use_mongodb=False,
    )


def run_task_with_mongodb(
    task: str,
    context: dict[str, Any] | None = None,
    *,
    target_app: str | None = None,
    db_subdir: str = _DEFAULT_DB_SUBDIR,
) -> tuple[str, list[str]]:
    """File tools + MongoDB MCP."""
    return run_task(
        task,
        context,
        target_app=target_app,
        db_subdir=db_subdir,
        use_postgres=False,
        use_mongodb=True,
    )


def run_task_with_postgres_and_mongodb(
    task: str,
    context: dict[str, Any] | None = None,
    *,
    target_app: str | None = None,
    db_subdir: str = _DEFAULT_DB_SUBDIR,
) -> tuple[str, list[str]]:
    """File tools + Postgres MCP + MongoDB MCP (sql/ and nosql/ respectively)."""
    return run_task(
        task,
        context,
        target_app=target_app,
        db_subdir=db_subdir,
        use_postgres=True,
        use_mongodb=True,
    )


def serve_a2a(
    host: str = "127.0.0.1",
    port: int = A2A_PORT,
    *,
    use_postgres: bool = False,
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
        tools = _build_toolset(stack, use_postgres=use_postgres, use_mongodb=use_mongodb)
        agent = _build_agent(tools)
        A2AServer(agent, host=host, port=port, skills=skills).serve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Database agent - Strands + Postgres/MongoDB MCP")
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
    parser.add_argument("--serve-a2a", action="store_true", help=f"Start A2A server on :{A2A_PORT}")
    parser.add_argument("--port", type=int, default=A2A_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    use_postgres = args.with_postgres
    use_mongodb = args.with_mongodb

    if args.serve_a2a:
        serve_a2a(host=args.host, port=args.port, use_postgres=use_postgres, use_mongodb=use_mongodb)
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

    task = args.task or DEFAULT_PIPELINE_TASK

    model_id = coding_model_id()
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
    if use_postgres:
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