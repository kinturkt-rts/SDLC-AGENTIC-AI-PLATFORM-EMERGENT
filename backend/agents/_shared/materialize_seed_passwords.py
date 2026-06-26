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
from sqlalchemy import create_engine, text


def count_invalid_hashes(
    target_app: str,
    repo_root: Path,
    creds: list[tuple[str, str, str, str]],
) -> int:
    if not creds:
        return 0
    schema = schema_for_app(target_app)
    _, hash_col = creds[0][2], creds[0][3]
    engine = create_engine(connection_url(), pool_pre_ping=True)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                f"SELECT COUNT(*) FROM {schema}.users "
                f"WHERE {hash_col} = :placeholder OR {hash_col} NOT LIKE '$2%'"
            ),
            {"placeholder": _PLACEHOLDER},
        ).fetchone()
    return int(row[0]) if row else 0


def materialize(
    target_app: str,
    repo_root: Path | None = None,
    *,
    strict: bool = True,
) -> list[str]:
    root = repo_root or _REPO_ROOT
    load_target_app_env(target_app, root)
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
    engine = create_engine(connection_url(), pool_pre_ping=True)
    updated = 0

    with engine.begin() as conn:
        for lookup_value, plaintext, lookup_col, hash_col in creds:
            digest = bcrypt.hashpw(
                plaintext.encode("utf-8"), bcrypt.gensalt(rounds=12)
            ).decode("utf-8")
            result = conn.execute(
                text(
                    f"UPDATE {schema}.users "
                    f"SET {hash_col} = :digest "
                    f"WHERE {lookup_col} = :lookup "
                    f"AND ({hash_col} = :placeholder OR {hash_col} NOT LIKE '$2%')"
                ),
                {
                    "digest": digest,
                    "lookup": lookup_value,
                    "placeholder": _PLACEHOLDER,
                },
            )
            updated += result.rowcount or 0

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
