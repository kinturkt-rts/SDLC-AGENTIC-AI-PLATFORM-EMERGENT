"""Materialize bcrypt / SHA-256 seed hashes on RDS after seed SQL (no LLM-computed hashes).

Database-agent writes ``__BCRYPT_PLACEHOLDER__`` (bcrypt.verify apps) or
``__SHA256_PLACEHOLDER:<label>__`` (opaque X-API-Key apps that store sha256 hex).
``apply_sql_to_rds.py`` preprocessing normally replaces both before INSERT. This
module verifies live RDS and repairs leftovers — including invented ``sha256_*``
fake tokens that never match a real digest lookup.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.rds_env import connection_url, load_target_app_env, schema_for_app

from _shared.seed_credentials import _PLACEHOLDER
from _shared.sha256_api_keys import (
    collect_documented_api_keys,
    is_sha256_placeholder_or_fake,
    sha256_hex,
)

from _shared.verify_seed_bcrypt import documented_password

import bcrypt
import psycopg
from psycopg import sql as psql


# Matches the bare placeholder AND per-row suffixed variants (e.g.
# __BCRYPT_PLACEHOLDER_VIEWER__), any case. Used with Postgres's case-insensitive
# ~* operator, not exact equality, so live rows holding a variant are still found.
_PLACEHOLDER_PG_RE = r"__BCRYPT_PLACEHOLDER(?:_[A-Za-z0-9]+)*__"
_LABELED_SHA256_RE = re.compile(r"^__SHA256_PLACEHOLDER:([A-Za-z0-9_-]+)__$")



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
                    psql.SQL("SELECT EXISTS (SELECT 1 FROM {}.{} WHERE {} ~* %s)").format(
                        psql.Identifier(schema),
                        psql.Identifier(table_name),
                        psql.Identifier(column_name),
                    ),
                    (_PLACEHOLDER_PG_RE,),
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
    """Hash each remaining bcrypt placeholder row in place, one fresh hash per row."""
    schema = schema_for_app(target_app)
    with _connect(connection_url()) as conn:
        with conn.cursor() as cur:
            for table_name, column_name in columns:
                cur.execute(
                    psql.SQL("SELECT ctid FROM {}.{} WHERE {} ~* %s").format(
                        psql.Identifier(schema),
                        psql.Identifier(table_name),
                        psql.Identifier(column_name),
                    ),
                    (_PLACEHOLDER_PG_RE,),
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


def _resolve_plaintext_for_hash_value(
    value: str,
    *,
    row_label: str | None,
    documented: dict[str, str],
) -> str | None:
    labeled = _LABELED_SHA256_RE.fullmatch((value or "").strip())
    if labeled:
        return documented.get(labeled.group(1))
    if row_label and row_label in documented:
        return documented[row_label]
    return None


def materialize_sha256_api_key_hashes(target_app: str, app_dir: Path) -> list[str]:
    """Replace leftover SHA-256 placeholders / fake ``sha256_*`` tokens on RDS.

    Prefers tables with a ``label`` column (api_keys pattern). Also resolves
    ``__SHA256_PLACEHOLDER:<label>__`` values without needing the label column.
    """
    documented = collect_documented_api_keys(app_dir)
    schema = schema_for_app(target_app)
    errors: list[str] = []
    updated = 0
    unresolved = 0

    with _connect(connection_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name, column_name FROM information_schema.columns
                WHERE table_schema = %s AND data_type IN ('text', 'character varying')
                """,
                (schema,),
            )
            text_cols = cur.fetchall()
            tables: dict[str, list[str]] = {}
            for table_name, column_name in text_cols:
                tables.setdefault(table_name, []).append(column_name)

            for table_name, columns in tables.items():
                has_label = "label" in columns
                for column_name in columns:
                    if column_name == "label":
                        continue
                    if has_label:
                        cur.execute(
                            psql.SQL(
                                "SELECT ctid, {}, label FROM {}.{} "
                                "WHERE {} IS NOT NULL"
                            ).format(
                                psql.Identifier(column_name),
                                psql.Identifier(schema),
                                psql.Identifier(table_name),
                                psql.Identifier(column_name),
                            )
                        )
                    else:
                        cur.execute(
                            psql.SQL(
                                "SELECT ctid, {}, NULL::text FROM {}.{} "
                                "WHERE {} IS NOT NULL"
                            ).format(
                                psql.Identifier(column_name),
                                psql.Identifier(schema),
                                psql.Identifier(table_name),
                                psql.Identifier(column_name),
                            )
                        )
                    for ctid, value, row_label in cur.fetchall():
                        if not is_sha256_placeholder_or_fake(str(value)):
                            continue
                        plaintext = _resolve_plaintext_for_hash_value(
                            str(value),
                            row_label=row_label,
                            documented=documented,
                        )
                        if not plaintext:
                            unresolved += 1
                            continue
                        cur.execute(
                            psql.SQL(
                                "UPDATE {}.{} SET {} = %s WHERE ctid = %s"
                            ).format(
                                psql.Identifier(schema),
                                psql.Identifier(table_name),
                                psql.Identifier(column_name),
                            ),
                            (sha256_hex(plaintext), ctid),
                        )
                        updated += 1
        conn.commit()

    if unresolved:
        errors.append(
            f"{target_app}: {unresolved} SHA-256 placeholder/fake key_hash row(s) "
            "could not be resolved — add `-- API key for <label>: \"…\"` comments "
            "matching api_keys.label (or use __SHA256_PLACEHOLDER:<label>__)"
        )
    if updated:
        print(
            f"[materialize] Updated {updated} SHA-256 API-key hash row(s) for {target_app}",
            file=sys.stderr,
        )
    return errors


def materialize(
    target_app: str,
    repo_root: Path | None = None,
    *,
    strict: bool = True,
) -> list[str]:
    """Ensure no live row still holds bcrypt or SHA-256 seed placeholders/fakes."""
    from _shared.pipeline_context import target_app_root_rel

    root = repo_root or _REPO_ROOT
    load_target_app_env(target_app, root)
    app_dir = root / target_app_root_rel(target_app)
    if not (app_dir / "db").is_dir():
        app_dir = root / "target-apps" / target_app

    errors: list[str] = []

    remaining = find_remaining_placeholder_columns(target_app)
    if remaining:
        password = _resolve_fallback_password(app_dir)
        _materialize_columns_in_place(target_app, remaining, password)
        still_remaining = find_remaining_placeholder_columns(target_app)
        if still_remaining and strict:
            locations = ", ".join(f"{t}.{c}" for t, c in still_remaining)
            errors.append(
                f"{target_app}: placeholder/invalid password hash still present in "
                f"{locations} after materialize (RDS login will 401)"
            )

    from _shared.sha256_api_keys import seed_sql_has_sha256_work

    if seed_sql_has_sha256_work(app_dir):
        sha_errors = materialize_sha256_api_key_hashes(target_app, app_dir)
        if sha_errors and strict:
            errors.extend(sha_errors)
        elif sha_errors:
            for msg in sha_errors:
                print(msg, file=sys.stderr)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize seed bcrypt / SHA-256 API-key hashes on RDS"
    )
    parser.add_argument("--target-app", required=True)
    parser.add_argument("--repo-root", default=str(_REPO_ROOT))
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="Do not fail when placeholders cannot be fully resolved",
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
