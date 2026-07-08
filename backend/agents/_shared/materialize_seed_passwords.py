"""Materialize bcrypt password hashes on RDS after seed SQL (no LLM-computed hashes).

Database-agent writes __BCRYPT_PLACEHOLDER__ in seed SQL. This runs automatically after
scripts/apply_sql_to_rds.py and UPDATEs live rows using bcrypt on a real CPU.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.rds_env import connection_url, load_target_app_env, schema_for_app
from _shared.seed_credentials import (
    _PLACEHOLDER,
    collect_credentials,
    seed_sql_has_placeholders,
)

import bcrypt
import psycopg
from psycopg import sql as psql


def _connect(conn_url: str) -> psycopg.Connection:
    return psycopg.connect(conn_url, autocommit=False)


def count_invalid_hashes(
    target_app: str,
    repo_root: Path,
    creds: list[tuple[str, str, str, str]],
) -> int:
    if not creds:
        return 0
    schema = schema_for_app(target_app)
    _, hash_col = creds[0][2], creds[0][3]
    with _connect(connection_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                psql.SQL(
                    "SELECT COUNT(*) FROM {schema}.users "
                    "WHERE {hash_col} = %s OR {hash_col} NOT LIKE '$2%%'"
                ).format(
                    schema=psql.Identifier(schema),
                    hash_col=psql.Identifier(hash_col),
                ),
                (str(_PLACEHOLDER),),
            )
            row = cur.fetchone()
    return int(row[0]) if row else 0


def materialize(
    target_app: str,
    repo_root: Path | None = None,
    *,
    strict: bool = True,
) -> list[str]:
    from _shared.pipeline_context import target_app_root_rel

    root = repo_root or _REPO_ROOT
    load_target_app_env(target_app, root)
    app_dir = root / target_app_root_rel(target_app)
    if not (app_dir / "db").is_dir():
        app_dir = root / "target-apps" / target_app

    creds = collect_credentials(app_dir)
    if not creds:
        if seed_sql_has_placeholders(app_dir):
            return [
                f"{target_app}: seed SQL has __BCRYPT_PLACEHOLDER__ but no login rows could be "
                "parsed (check users INSERT columns and password comment in *_seed.sql)"
            ]
        return []

    schema = schema_for_app(target_app)
    updated = 0

    with _connect(connection_url()) as conn:
        with conn.cursor() as cur:
            for lookup_value, plaintext, lookup_col, hash_col in creds:
                digest = bcrypt.hashpw(
                    plaintext.encode("utf-8"), bcrypt.gensalt(rounds=12)
                ).decode("utf-8")
                cur.execute(
                    psql.SQL(
                        "UPDATE {schema}.users "
                        "SET {hash_col} = %s "
                        "WHERE {lookup_col} = %s "
                        "AND ({hash_col} = %s OR {hash_col} NOT LIKE '$2%%')"
                    ).format(
                        schema=psql.Identifier(schema),
                        hash_col=psql.Identifier(hash_col),
                        lookup_col=psql.Identifier(lookup_col),
                    ),
                    (digest, lookup_value, str(_PLACEHOLDER)),
                )
                updated += cur.rowcount or 0
        conn.commit()

    remaining = count_invalid_hashes(target_app, root, creds)
    if remaining > 0 and strict:
        return [
            f"{target_app}: {remaining} user row(s) still have placeholder/invalid password "
            f"hash after materialize in schema {schema!r} (RDS login will 401)"
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
