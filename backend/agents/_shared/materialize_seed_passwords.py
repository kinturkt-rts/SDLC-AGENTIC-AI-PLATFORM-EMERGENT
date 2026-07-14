"""Materialize bcrypt password hashes on RDS after seed SQL (no LLM-computed hashes).

Database-agent writes __BCRYPT_PLACEHOLDER__ in seed SQL. apply_sql_to_rds.py's own
pre-apply preprocessing already replaces every occurrence with a freshly-salted bcrypt
hash directly in the INSERT text, regardless of which table/column it lands in — so by
the time this module runs, RDS should already have zero placeholders. This module's
primary job is therefore to VERIFY that against live RDS (schema-agnostic: scans every
text-like column, not just users.password_hash), and only falls back to hashing rows
in place if verification finds the preprocessing did not run (e.g. bcrypt missing at
apply time). Neither path depends on parsing seed SQL for a login-identifying column —
that used to be required and broke on every schema shape (integer PKs, no login column,
UNIQUE-constrained hash columns) that database-agent produced but this parser didn't
anticipate. See _shared/seed_credentials.py for the legacy parser, still used for
optional HANDOFF.md credential documentation and QA login verification, never as a
pipeline-blocking gate.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.rds_env import connection_url, load_target_app_env, schema_for_app
from _shared.seed_credentials import _PLACEHOLDER
from _shared.verify_seed_bcrypt import documented_password

import bcrypt
import psycopg
from psycopg import sql as psql


def _connect(conn_url: str) -> psycopg.Connection:
    return psycopg.connect(conn_url, autocommit=False)


def find_remaining_placeholder_columns(target_app: str) -> list[tuple[str, str]]:
    """Scan every text-like column in the app's live schema for the literal placeholder.

    Schema-agnostic by construction: it asks Postgres which columns exist and checks
    each one directly, rather than guessing table/column names or requiring a
    login-identifying column to exist. Returns [] when apply_sql_to_rds.py's
    preprocessing already replaced every occurrence (the expected, common case).
    """
    schema = schema_for_app(target_app)
    hits: list[tuple[str, str]] = []
    with _connect(connection_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name, column_name FROM information_schema.columns
                WHERE table_schema = %s AND data_type IN ('text', 'character varying')
                """,
                (schema,),
            )
            candidates = cur.fetchall()
            for table_name, column_name in candidates:
                cur.execute(
                    psql.SQL("SELECT EXISTS (SELECT 1 FROM {}.{} WHERE {} = %s)").format(
                        psql.Identifier(schema),
                        psql.Identifier(table_name),
                        psql.Identifier(column_name),
                    ),
                    (_PLACEHOLDER,),
                )
                if cur.fetchone()[0]:
                    hits.append((table_name, column_name))
    return hits


def _resolve_fallback_password(app_dir: Path) -> str:
    sql_dir = app_dir / "db" / "sql"
    if sql_dir.is_dir():
        for seed in sorted(sql_dir.glob("*seed*.sql")):
            if "fix" in seed.name.lower():
                continue
            password = documented_password(seed.read_text(encoding="utf-8"))
            if password:
                return password
    return os.environ.get("SDLC_DEFAULT_SEED_PASSWORD", "DevPass123!")


def _materialize_columns_in_place(
    target_app: str,
    columns: list[tuple[str, str]],
    password: str,
) -> None:
    """Hash each remaining placeholder row in place, one fresh hash per physical row.

    Uses Postgres's built-in `ctid` (physical row identity) instead of a primary key
    column, so this needs zero knowledge of table shape — no PK type, no login column,
    no schema-specific parsing. Each row gets its own salted hash so UNIQUE-constrained
    columns (e.g. api_keys.key_hash) never collide the way a single shared hash would.
    """
    schema = schema_for_app(target_app)
    with _connect(connection_url()) as conn:
        with conn.cursor() as cur:
            for table_name, column_name in columns:
                cur.execute(
                    psql.SQL("SELECT ctid FROM {}.{} WHERE {} = %s").format(
                        psql.Identifier(schema),
                        psql.Identifier(table_name),
                        psql.Identifier(column_name),
                    ),
                    (_PLACEHOLDER,),
                )
                rows = cur.fetchall()
                for (ctid,) in rows:
                    digest = bcrypt.hashpw(
                        password.encode("utf-8"), bcrypt.gensalt(rounds=12)
                    ).decode("utf-8")
                    cur.execute(
                        psql.SQL("UPDATE {}.{} SET {} = %s WHERE ctid = %s").format(
                            psql.Identifier(schema),
                            psql.Identifier(table_name),
                            psql.Identifier(column_name),
                        ),
                        (digest, ctid),
                    )
        conn.commit()


def materialize(
    target_app: str,
    repo_root: Path | None = None,
    *,
    strict: bool = True,
) -> list[str]:
    """Ensure no live row in the app's schema still holds the literal placeholder.

    Schema-agnostic: this checks and (if needed) fixes RDS directly via
    find_remaining_placeholder_columns(), which discovers table/column shape from
    information_schema rather than assuming a users table with a specific PK type
    or a login-identifying column. In the common case apply_sql_to_rds.py's own
    pre-apply preprocessing already replaced every occurrence, so this returns []
    immediately without touching RDS again.
    """
    from _shared.pipeline_context import target_app_root_rel

    root = repo_root or _REPO_ROOT
    load_target_app_env(target_app, root)
    app_dir = root / target_app_root_rel(target_app)
    if not (app_dir / "db").is_dir():
        app_dir = root / "target-apps" / target_app

    remaining = find_remaining_placeholder_columns(target_app)
    if not remaining:
        return []

    password = _resolve_fallback_password(app_dir)
    _materialize_columns_in_place(target_app, remaining, password)

    still_remaining = find_remaining_placeholder_columns(target_app)
    if still_remaining and strict:
        locations = ", ".join(f"{t}.{c}" for t, c in still_remaining)
        return [
            f"{target_app}: placeholder/invalid password hash still present in "
            f"{locations} after materialize (RDS login will 401)"
        ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize seed bcrypt hashes on RDS")
    parser.add_argument("--target-app", required=True)
    parser.add_argument("--repo-root", default=str(_REPO_ROOT))
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="Do not fail when no rows updated (already materialized)",
    )
    args = parser.parse_args()

    try:
        errors = materialize(
            args.target_app,
            Path(args.repo_root),
            strict=not args.no_strict,
        )
    except Exception as exc:
        print(f"materialize_seed_passwords failed: {exc}", file=sys.stderr)
        return 1

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1

    print(f"seed passwords materialized on RDS: {args.target_app}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
