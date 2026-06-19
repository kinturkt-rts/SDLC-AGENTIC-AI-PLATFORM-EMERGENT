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


def resolve_app_schema(target_app: str | None) -> str | None:
    """Postgres schema for unqualified DDL/DML (meeting-assistant → meeting_assistant)."""
    explicit = os.environ.get("POSTGRES_APP_SCHEMA", "").strip()
    if explicit:
        return explicit
    if target_app:
        return target_app.strip().replace("-", "_")
    return None


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


def apply_sql_files(
    sql_dir: Path,
    *,
    target_app: str | None = None,
    skip_seed: bool = False,
    dry_run: bool = False,
    quiet: bool = False,
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
                if app_schema:
                    _ensure_schema_and_search_path(cur, app_schema)
                applied: list[str] = []
                for path in files:
                    sql = path.read_text(encoding="utf-8").strip()
                    if not sql:
                        print(f"SKIP (empty): {path.name}", file=sys.stderr)
                        continue
                    if verbose:
                        print(f"Applying {path.name} ...", file=sys.stderr)
                    for stmt in split_sql_statements(sql):
                        cur.execute(stmt)
                    applied.append(path.name)
                    if verbose:
                        print("  OK", file=sys.stderr)

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

    if target_app and not skip_seed:
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
    args = parser.parse_args()

    if args.sql_dir:
        sql_dir = args.sql_dir if args.sql_dir.is_absolute() else _REPO_ROOT / args.sql_dir
    elif args.target_app:
        sql_dir = _REPO_ROOT / "target-apps" / args.target_app / "db" / "sql"
    else:
        parser.error("Provide --target-app or --sql-dir")
        return 2

    quiet = args.quiet and not args.verbose
    return apply_sql_files(
        sql_dir,
        target_app=args.target_app,
        skip_seed=args.skip_seed,
        dry_run=args.dry_run,
        quiet=quiet,
    )


if __name__ == "__main__":
    raise SystemExit(main())
