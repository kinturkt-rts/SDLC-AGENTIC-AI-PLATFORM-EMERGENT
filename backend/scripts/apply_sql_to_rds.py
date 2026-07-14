"""Apply target-app SQL migrations to RDS — no Bedrock, no MCP SQL filters.

The Postgres MCP `run_query` tool blocks migration-style SQL (multi-statement
scripts, GRANT/REVOKE, SET search_path). This script connects with psycopg using
DATABASE_URL or POSTGRES_MCP_* from .env.local and runs sql/ files in order.

Usage (from repo root):
  aws sso login --profile eks-admin-user
  python scripts/apply_sql_to_rds.py --target-app meeting-assistant
  python scripts/apply_sql_to_rds.py --target-app finops-web-app

Schema: derived from --target-app (hyphens → underscores). Sets search_path so unqualified
sql/ DDL/DML land in that schema, not public. Override only with POSTGRES_APP_SCHEMA if needed.
"""

from __future__ import annotations

import argparse
import os
import re
import socket
import sys
from pathlib import Path
from urllib.parse import quote_plus

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.env import load_repo_env

load_repo_env()

_DOLLAR_BLOCK = re.compile(r"\$\$.*?\$\$", re.DOTALL)

# Matches bare pg_type typname checks that lack a schema (nspname) filter.
# On a shared RDS instance with multiple app schemas the same type name can exist in several
# schemas.  "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'foo')" finds the type in
# ANY schema and skips creation in the current schema, causing the following CREATE TABLE to fail.
_BARE_TYPE_CHECK_RE = re.compile(
    r"IF\s+NOT\s+EXISTS\s*"
    r"\(\s*SELECT\s+1\s+FROM\s+pg_type\s+WHERE\s+typname\s*=\s*('[^']+')\s*\)",
    re.IGNORECASE | re.DOTALL,
)
_SCHEMA_QUALIFIED_TYPE_CHECK = (
    r"IF NOT EXISTS ("
    r"SELECT 1 FROM pg_type t "
    r"JOIN pg_namespace n ON n.oid = t.typnamespace "
    r"WHERE t.typname = \1 AND n.nspname = current_schema()"
    r")"
)


def _patch_type_existence_checks(stmt: str) -> str:
    """Rewrite bare pg_type IF NOT EXISTS checks to be schema-qualified.

    Prevents false-positive EXISTS on shared RDS: the same type name (user_role, etc.) can exist
    in other app schemas.  Adds AND n.nspname = current_schema() so each app only sees its own.
    """
    if "pg_type" not in stmt:
        return stmt
    return _BARE_TYPE_CHECK_RE.sub(_SCHEMA_QUALIFIED_TYPE_CHECK, stmt)


def resolve_app_schema(target_app: str | None) -> str | None:
    """Postgres schema for unqualified DDL/DML (meeting-assistant → meeting_assistant)."""
    explicit = os.environ.get("POSTGRES_APP_SCHEMA", "").strip()
    if explicit:
        return explicit
    if target_app:
        return target_app.strip().replace("-", "_")
    return None


_PGVECTOR_SQL_MARKERS = (
    " vector(",
    " vector_cosine_ops",
    " vector_l2_ops",
    "create extension if not exists vector",
    "using hnsw",
)

_PGTRGM_SQL_MARKERS = (
    "gin_trgm_ops",
    "gist_trgm_ops",
    "similarity(",
    "create extension if not exists pg_trgm",
)


def _sql_files_need_pgvector(files: list[Path]) -> bool:
    """True when migrations use pgvector types, indexes, or extension DDL."""
    for path in files:
        lowered = path.read_text(encoding="utf-8").lower()
        if any(marker in lowered for marker in _PGVECTOR_SQL_MARKERS):
            return True
    return False


def _sql_files_need_pgtrgm(files: list[Path]) -> bool:
    """True when migrations use pg_trgm operators/opclasses or extension DDL."""
    for path in files:
        lowered = path.read_text(encoding="utf-8").lower()
        if any(marker in lowered for marker in _PGTRGM_SQL_MARKERS):
            return True
    return False


def _vector_type_schema(cur) -> str | None:
    cur.execute(
        """
        SELECT n.nspname
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'vector' AND t.typtype = 'b'
        LIMIT 1
        """
    )
    row = cur.fetchone()
    return row[0] if row else None


def _ensure_pgvector_extension(cur, *, verbose: bool) -> None:
    """Install pgvector in public before any VECTOR(...) DDL (required on shared RDS)."""
    type_schema = _vector_type_schema(cur)
    if type_schema is None:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")
        type_schema = _vector_type_schema(cur)
    elif type_schema != "public":
        if verbose:
            print(
                f"  Relocating pgvector from {type_schema} to public (shared RDS) ...",
                file=sys.stderr,
            )
        cur.execute("ALTER EXTENSION vector SET SCHEMA public")
        type_schema = _vector_type_schema(cur)

    if type_schema != "public":
        raise RuntimeError(
            'pgvector type "vector" is not available in schema public. '
            f"Found in {type_schema!r} instead. "
            "On RDS, run: ALTER EXTENSION vector SET SCHEMA public; "
            "or contact a DBA to relocate the extension."
        )
    if verbose:
        print("  pgvector extension OK (schema public)", file=sys.stderr)


def _trgm_opclass_schema(cur) -> str | None:
    cur.execute(
        """
        SELECT n.nspname
        FROM pg_opclass opc
        JOIN pg_am am ON am.oid = opc.opcmethod
        JOIN pg_namespace n ON n.oid = opc.opcnamespace
        WHERE opc.opcname = 'gin_trgm_ops'
          AND am.amname = 'gin'
        LIMIT 1
        """
    )
    row = cur.fetchone()
    return row[0] if row else None


def _ensure_pgtrgm_extension(cur, *, verbose: bool) -> None:
    """Install pg_trgm in public before trigram index DDL.

    On shared RDS, `CREATE EXTENSION IF NOT EXISTS pg_trgm` can no-op because
    another app schema already owns the extension. Then `gin_trgm_ops` is not
    visible from the current app schema search_path and trigram indexes fail.
    """
    opclass_schema = _trgm_opclass_schema(cur)
    if opclass_schema is None:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public")
        opclass_schema = _trgm_opclass_schema(cur)
    elif opclass_schema != "public":
        if verbose:
            print(
                f"  Relocating pg_trgm from {opclass_schema} to public (shared RDS) ...",
                file=sys.stderr,
            )
        cur.execute("ALTER EXTENSION pg_trgm SET SCHEMA public")
        opclass_schema = _trgm_opclass_schema(cur)

    if opclass_schema != "public":
        raise RuntimeError(
            'pg_trgm operator class "gin_trgm_ops" is not available in schema public. '
            f"Found in {opclass_schema!r} instead. "
            "On RDS, run: ALTER EXTENSION pg_trgm SET SCHEMA public; "
            "or contact a DBA to relocate the extension."
        )
    if verbose:
        print("  pg_trgm extension OK (schema public)", file=sys.stderr)


def _is_verbose() -> bool:
    return os.getenv("APPLY_SQL_VERBOSE", os.getenv("DATABASE_AGENT_VERBOSE", "")).strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _preflight_aws(*, verbose: bool) -> bool:
    region = os.environ.get("AWS_REGION", os.environ.get("POSTGRES_MCP_REGION", "us-east-2"))
    try:
        import boto3

        ident = boto3.client("sts", region_name=region).get_caller_identity()
        if verbose:
            profile = os.environ.get("AWS_PROFILE", "(not set)")
            print(f"AWS_PROFILE={profile}  AWS_REGION={region}", file=sys.stderr)
            print(f"Caller: {ident.get('Arn', ident)}", file=sys.stderr)
        return True
    except Exception as exc:
        print(f"AWS credential check FAILED: {exc}", file=sys.stderr)
        return False


def _resolve_host_port(conn_url: str) -> tuple[str, int]:
    """Host/port for TCP probe. Prefer POSTGRES_MCP_*; passwords with @ break urlparse."""
    env_host = os.environ.get("POSTGRES_MCP_DB_ENDPOINT", "").strip()
    env_port = os.environ.get("POSTGRES_MCP_PORT", "5432").strip()
    if env_host:
        return env_host, int(env_port)

    if "@" not in conn_url:
        raise ValueError("Could not parse database host from connection URL")

    authority = conn_url.rsplit("@", 1)[-1].split("/")[0].split("?")[0]
    if ":" in authority:
        host, _, port_str = authority.rpartition(":")
        if not host:
            raise ValueError("Could not parse database host from connection URL")
        return host, int(port_str)
    return authority, 5432


def _tcp_probe(host: str, port: int, *, timeout: float | None = None) -> tuple[bool, str]:
    if timeout is None:
        timeout = float(os.getenv("POSTGRES_TCP_TIMEOUT", "5"))
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "reachable"
    except OSError as exc:
        return False, str(exc)


def _connection_url() -> str:
    host = os.environ.get("POSTGRES_MCP_DB_ENDPOINT", "").strip()
    database = os.environ.get("POSTGRES_MCP_DATABASE", "").strip()
    user = os.environ.get("POSTGRES_MCP_DB_USER", "postgres").strip()
    password = os.environ.get("POSTGRES_MCP_DB_PASSWORD", "").strip()
    port = os.environ.get("POSTGRES_MCP_PORT", "5432").strip()
    sslmode = os.environ.get("POSTGRES_MCP_SSLMODE", "require").strip()

    if host and database and password:
        safe_user = quote_plus(user)
        safe_password = quote_plus(password)
        return (
            f"postgresql://{safe_user}:{safe_password}@{host}:{port}/{database}"
            f"?sslmode={sslmode}"
        )

    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url

    raise ValueError(
        "Set POSTGRES_MCP_DB_ENDPOINT + POSTGRES_MCP_DATABASE + POSTGRES_MCP_DB_PASSWORD "
        "in .env.local (preferred), or a URL-encoded DATABASE_URL"
    )


def sorted_sql_files(sql_dir: Path, *, skip_seed: bool = False) -> list[Path]:
    if not sql_dir.is_dir():
        raise FileNotFoundError(f"SQL directory not found: {sql_dir}")
    files = sorted(sql_dir.glob("*.sql"), key=lambda p: p.name)
    if skip_seed:
        files = [f for f in files if "seed" not in f.name.lower()]
    if not files:
        raise FileNotFoundError(f"No .sql files in {sql_dir}")
    return files


def split_sql_statements(sql: str) -> list[str]:
    """Split SQL on semicolons outside strings and DO $$ ... $$ blocks."""
    lines: list[str] = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)

    protected = cleaned
    placeholders: dict[str, str] = {}

    for idx, match in enumerate(_DOLLAR_BLOCK.finditer(cleaned)):
        key = f"__DOLLAR_BLOCK_{idx}__"
        placeholders[key] = match.group(0)
        protected = protected.replace(match.group(0), key, 1)

    statements: list[str] = []
    current: list[str] = []
    in_single = False
    i = 0
    while i < len(protected):
        ch = protected[i]
        if ch == "'" and not in_single:
            in_single = True
            current.append(ch)
        elif ch == "'" and in_single:
            if i + 1 < len(protected) and protected[i + 1] == "'":
                current.append("''")
                i += 1
            else:
                in_single = False
                current.append(ch)
        elif ch == ";" and not in_single:
            piece = "".join(current).strip()
            if piece:
                for key, value in placeholders.items():
                    piece = piece.replace(key, value)
                statements.append(piece)
            current = []
        else:
            current.append(ch)
        i += 1

    tail = "".join(current).strip()
    if tail:
        for key, value in placeholders.items():
            tail = tail.replace(key, value)
        statements.append(tail)
    return statements


def _ensure_schema_and_search_path(cur: object, schema: str) -> None:
    from psycopg import sql as psql

    cur.execute(psql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(psql.Identifier(schema)))
    cur.execute(psql.SQL("SET search_path TO {}, public").format(psql.Identifier(schema), psql.Identifier("public")))


def _print_schema_row_counts(cur: object, schema: str) -> None:
    from psycopg import sql as psql

    cur.execute(
        """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = %s
        ORDER BY tablename
        """,
        (schema,),
    )
    tables = [row[0] for row in cur.fetchall()]
    if not tables:
        print(f"\nNo tables in schema {schema!r} after apply.", file=sys.stderr)
        return
    print(f"\nRow counts in {schema}:", file=sys.stderr)
    for table in tables:
        cur.execute(
            psql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                psql.Identifier(schema),
                psql.Identifier(table),
            )
        )
        count = cur.fetchone()[0]
        print(f"  {schema}.{table}: {count}", file=sys.stderr)


def _validate_sql_artifacts(sql_dir: Path) -> list[str]:
    from _shared.validate_sql_artifacts import validate_sql_dir

    return validate_sql_dir(sql_dir)


def _is_seed_file(path: Path) -> bool:
    return "seed" in path.name.lower()


_BCRYPT_PLACEHOLDER = "__BCRYPT_PLACEHOLDER__"


def _preprocess_seed_sql(sql: str) -> str:
    """Replace __BCRYPT_PLACEHOLDER__ with a real bcrypt hash before executing.

    Eliminates the fragile post-apply UPDATE pass: the hash is embedded directly
    in the INSERT so rows always land with a valid bcrypt string, never a placeholder.
    All seed users share one hash (same dev password); bcrypt.checkpw still works
    because the salt is stored in the hash string itself.
    """
    placeholder_sq = f"'{_BCRYPT_PLACEHOLDER}'"
    placeholder_dq = f'"{_BCRYPT_PLACEHOLDER}"'
    if placeholder_sq not in sql and placeholder_dq not in sql:
        return sql

    try:
        import bcrypt
    except ImportError:
        print(
            "[apply-sql] WARN: bcrypt not installed — __BCRYPT_PLACEHOLDER__ not replaced",
            file=sys.stderr,
        )
        return sql

    password: str | None = None
    try:
        from _shared.verify_seed_bcrypt import documented_password
        password = documented_password(sql)
    except ImportError:
        pass

    if not password:
        password = os.environ.get("SDLC_DEFAULT_SEED_PASSWORD", "DevPass123!")
        source = "SDLC_DEFAULT_SEED_PASSWORD env" if os.environ.get("SDLC_DEFAULT_SEED_PASSWORD") else "built-in default"
        print(
            f"[apply-sql] No documented password comment in seed SQL — using {source}",
            file=sys.stderr,
        )

    digest = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    result = sql.replace(placeholder_sq, f"'{digest}'").replace(placeholder_dq, f'"{digest}"')
    replaced = (sql.count(placeholder_sq) + sql.count(placeholder_dq)) - (
        result.count(placeholder_sq) + result.count(placeholder_dq)
    )
    print(
        f"[apply-sql] Pre-processed seed SQL: replaced {replaced} __BCRYPT_PLACEHOLDER__ occurrence(s) with bcrypt hash",
        file=sys.stderr,
    )
    return result


def apply_sql_files(
    sql_dir: Path,
    *,
    target_app: str | None = None,
    skip_seed: bool = False,
    skip_seed_materialize: bool = False,
    dry_run: bool = False,
    quiet: bool = False,
    reset_schema: bool = False,
) -> int:
    verbose = not quiet or _is_verbose()
    if not _preflight_aws(verbose=verbose):
        return 1

    try:
        conn_url = _connection_url()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    files = sorted_sql_files(sql_dir, skip_seed=skip_seed)
    app_schema = resolve_app_schema(target_app)

    pre_errors = _validate_sql_artifacts(sql_dir)
    if pre_errors:
        for err in pre_errors:
            print(f"FAILED (sql validation): {err}", file=sys.stderr)
        print(
            "Fix schema/seed nullability in db/sql/ before RDS apply. "
            "Optional columns must omit NOT NULL when seed uses NULL.",
            file=sys.stderr,
        )
        return 1

    host, port = _resolve_host_port(conn_url)
    host_hint = f"{host}:{port}"
    schema_label = app_schema or "public"
    if verbose:
        print(f"Target RDS: {host_hint}", file=sys.stderr)
        if app_schema:
            print(f"App schema   : {app_schema}", file=sys.stderr)
        print(f"SQL dir: {sql_dir}  ({len(files)} file(s))", file=sys.stderr)
        for path in files:
            print(f"  - {path.name}", file=sys.stderr)
    else:
        print(
            f"[apply-sql] {schema_label} @ {host_hint} — {len(files)} file(s)",
            file=sys.stderr,
        )

    if dry_run:
        print("Dry run — no database calls.", file=sys.stderr)
        return 0

    try:
        import psycopg
    except ImportError:
        print("Install psycopg: pip install 'psycopg[binary]'", file=sys.stderr)
        return 1

    tcp_ok, tcp_msg = _tcp_probe(host, port)
    if not tcp_ok:
        print(f"FAILED: cannot reach {host}:{port} ({tcp_msg})", file=sys.stderr)
        print(
            "RDS apply needs network access to port 5432. If this worked yesterday, "
            "your public IP may have changed — security groups often allow only one IP.",
            file=sys.stderr,
        )
        print("Diagnose: python scripts/check_rds_network.py", file=sys.stderr)
        print(
            "After SQL files exist locally, retry without Bedrock:\n"
            f"  python scripts/apply_sql_to_rds.py --target-app {target_app or '<app>'} --verbose",
            file=sys.stderr,
        )
        return 1

    connect_timeout = int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "15"))

    try:
        with psycopg.connect(conn_url, autocommit=True, connect_timeout=connect_timeout) as conn:
            with conn.cursor() as cur:
                if app_schema and reset_schema:
                    from psycopg import sql as psql
                    if verbose:
                        print(f"Resetting schema {app_schema!r} (DROP CASCADE + CREATE) ...", file=sys.stderr)
                    cur.execute(psql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(psql.Identifier(app_schema)))
                    cur.execute(psql.SQL("CREATE SCHEMA {}").format(psql.Identifier(app_schema)))
                    cur.execute(psql.SQL("SET search_path TO {}, public").format(psql.Identifier(app_schema), psql.Identifier("public")))
                if app_schema:
                    _ensure_schema_and_search_path(cur, app_schema)
                if _sql_files_need_pgvector(files):
                    if verbose:
                        print("Ensuring pgvector extension (public) ...", file=sys.stderr)
                    _ensure_pgvector_extension(cur, verbose=verbose)
                if _sql_files_need_pgtrgm(files):
                    if verbose:
                        print("Ensuring pg_trgm extension (public) ...", file=sys.stderr)
                    _ensure_pgtrgm_extension(cur, verbose=verbose)
                applied: list[str] = []
                ddl_files = [f for f in files if not _is_seed_file(f)]
                seed_files = [f for f in files if _is_seed_file(f)]
                if skip_seed:
                    seed_files = []

                def _apply_paths(paths: list[Path], *, label: str) -> None:
                    nonlocal applied
                    for path in paths:
                        sql = path.read_text(encoding="utf-8").strip()
                        if not sql:
                            print(f"SKIP (empty): {path.name}", file=sys.stderr)
                            continue
                        if label == "seed":
                            sql = _preprocess_seed_sql(sql)
                        if verbose:
                            print(f"Applying {path.name} ...", file=sys.stderr)
                        for stmt in split_sql_statements(sql):
                            cur.execute(_patch_type_existence_checks(stmt))
                        applied.append(path.name)
                        if verbose:
                            print("  OK", file=sys.stderr)

                _apply_paths(ddl_files, label="ddl")
                if app_schema and ddl_files:
                    from _shared.validate_sql_artifacts import reconcile_nullability_from_ddl

                    reconciled = reconcile_nullability_from_ddl(
                        cur,
                        app_schema=app_schema,
                        sql_dir=sql_dir,
                        verbose=verbose,
                    )
                    if reconciled and not verbose:
                        print(
                            f"[apply-sql] Reconciled {len(reconciled)} nullable column(s) on RDS",
                            file=sys.stderr,
                        )
                _apply_paths(seed_files, label="seed")

                if app_schema and verbose:
                    _print_schema_row_counts(cur, app_schema)
                    cur.execute(
                        """
                        SELECT schemaname, tablename
                        FROM pg_tables
                        WHERE schemaname = 'public'
                          AND tablename IN (
                            SELECT tablename FROM pg_tables WHERE schemaname = %s
                          )
                        ORDER BY tablename
                        """,
                        (app_schema,),
                    )
                    dup_public = cur.fetchall()
                    if dup_public:
                        print(
                            f"\nNote: duplicate table names also exist in public "
                            f"(data may be there if {app_schema} counts are 0).",
                            file=sys.stderr,
                        )
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    if not verbose and applied:
        print(f"[apply-sql] Applied: {', '.join(applied)}", file=sys.stderr)
    print("[apply-sql] Done.", file=sys.stderr)

    if target_app and not skip_seed and not skip_seed_materialize:
        app_schema = resolve_app_schema(target_app)
        if app_schema:
            os.environ["POSTGRES_APP_SCHEMA"] = app_schema
        if _materialize_seed_passwords(target_app) != 0:
            return 1

    return 0


def _materialize_seed_passwords(target_app: str) -> int:
    """Replace __BCRYPT_PLACEHOLDER__ rows on RDS immediately after seed SQL apply."""
    agents_dir = _REPO_ROOT / "agents"
    if str(agents_dir) not in sys.path:
        sys.path.insert(0, str(agents_dir))
    try:
        from _shared.materialize_seed_passwords import materialize
        from _shared.seed_credentials import seed_sql_has_placeholders
    except ImportError as exc:
        print(f"[apply-sql] WARN: could not import materialize ({exc})", file=sys.stderr)
        return 0

    try:
        from _shared.pipeline_context import target_app_root_rel
        app_dir = _REPO_ROOT / target_app_root_rel(target_app)
    except ImportError:
        app_dir = _REPO_ROOT / "target-apps" / target_app
    if not (app_dir / "db").is_dir():
        app_dir = _REPO_ROOT / "target-apps" / target_app
    if not seed_sql_has_placeholders(app_dir):
        return 0

    print("[apply-sql] Materializing seed bcrypt passwords on RDS ...", file=sys.stderr)
    try:
        errors = materialize(target_app, _REPO_ROOT, strict=True)
    except Exception as exc:
        print(f"[apply-sql] FAILED: materialize_seed_passwords: {exc}", file=sys.stderr)
        return 1
    if errors:
        for err in errors:
            print(f"[apply-sql] FAILED: {err}", file=sys.stderr)
        return 1
    print("[apply-sql] Seed passwords materialized (RDS login ready).", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply target-app sql/ migrations to RDS (psycopg, no Bedrock).",
    )
    parser.add_argument(
        "--target-app",
        help="App folder under target-apps/ (uses target-apps/<app>/db/sql)",
    )
    parser.add_argument(
        "--sql-dir",
        type=Path,
        help="Explicit path to sql/ folder (overrides --target-app)",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip files with 'seed' in the name",
    )
    parser.add_argument(
        "--skip-seed-materialize",
        action="store_true",
        help="Apply SQL only; do not run materialize_seed_passwords (orchestrator runs it separately)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files only; do not connect or execute",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal stderr (default when invoked from database-agent)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Full AWS caller, SQL dir listing, per-file apply lines",
    )
    parser.add_argument(
        "--reset-schema",
        action="store_true",
        help="DROP SCHEMA CASCADE then recreate before applying (for fresh pipeline runs)",
    )
    args = parser.parse_args()

    if args.sql_dir:
        sql_dir = args.sql_dir if args.sql_dir.is_absolute() else _REPO_ROOT / args.sql_dir
    elif args.target_app:
        try:
            from _shared.pipeline_context import target_app_root_rel
            sql_dir = _REPO_ROOT / target_app_root_rel(args.target_app) / "db" / "sql"
        except ImportError:
            sql_dir = _REPO_ROOT / "target-apps" / args.target_app / "db" / "sql"
        if not sql_dir.is_dir():
            sql_dir = _REPO_ROOT / "target-apps" / args.target_app / "db" / "sql"
    else:
        parser.error("Provide --target-app or --sql-dir")
        return 2

    quiet = args.quiet and not args.verbose
    return apply_sql_files(
        sql_dir,
        target_app=args.target_app,
        skip_seed=args.skip_seed,
        skip_seed_materialize=args.skip_seed_materialize,
        dry_run=args.dry_run,
        quiet=quiet,
        reset_schema=args.reset_schema,
    )


if __name__ == "__main__":
    raise SystemExit(main())
