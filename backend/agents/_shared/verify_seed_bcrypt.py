"""Verify dev seed SQL bcrypt hashes and (optionally) hashes stored on RDS.

Catches the #1 false-green: pytest passes via conftest hash_password() while RDS seed SQL
has a placeholder bcrypt string — Swagger/Streamlit login returns 401.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import bcrypt

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

# e.g. Password for all seed users: "AuditPass123!"  OR  -- Password: AssetPass123!
_PASSWORD_COMMENT_RE = re.compile(
    r'(?:Password|passwords?)[^"\n]*(?:"([^"]+)"|: *([^\s!][^\n]*!))',
    re.IGNORECASE,
)
_BCRYPT_HASH_RE = re.compile(r"\$2[aby]\$12\$[./A-Za-z0-9]{53}")
# First user row in seed INSERT: ('uuid', 'username', '$2b$12$...')
_SEED_USERNAME_RE = re.compile(
    r"\('[0-9a-f-]{36}',\s*'([^']+)',\s*'\$2[aby]\$12\$",
    re.IGNORECASE,
)
# Dollar-quoting bcrypt breaks the leading $ (stored as 2b$12$...)
_DOLLAR_QUOTED_BCRYPT_RE = re.compile(
    r"\$[a-zA-Z_]+\$2[aby]\$12\$",
    re.IGNORECASE,
)
_PLACEHOLDER = "__BCRYPT_PLACEHOLDER__"


def seed_targets_user_passwords(seed_text: str) -> bool:
    """True when seed SQL inserts into password_hash / hashed_password columns."""
    lowered = seed_text.lower()
    return "password_hash" in lowered or "hashed_password" in lowered


def documented_password(seed_text: str) -> str | None:
    match = _PASSWORD_COMMENT_RE.search(seed_text)
    if not match:
        return None
    return (match.group(1) or match.group(2) or "").strip() or None


def first_seed_username(seed_text: str) -> str | None:
    match = _SEED_USERNAME_RE.search(seed_text)
    return match.group(1) if match else None


def bcrypt_hashes(seed_text: str) -> set[str]:
    return set(_BCRYPT_HASH_RE.findall(seed_text))


def scan_sql_antipatterns(path: Path) -> list[str]:
    """Flag dollar-quoted bcrypt (PostgreSQL strips leading $)."""
    text = path.read_text(encoding="utf-8")
    if "password_hash" not in text.lower() and "hashed_password" not in text.lower():
        return []
    if _DOLLAR_QUOTED_BCRYPT_RE.search(text):
        return [
            f"{path}: dollar-quoted bcrypt hash will corrupt the leading '$' on apply — "
            "use single-quoted '$2b$12$...' literals instead"
        ]
    return []


def verify_seed_file(path: Path) -> list[str]:
    errors = scan_sql_antipatterns(path)
    text = path.read_text(encoding="utf-8")
    if not seed_targets_user_passwords(text):
        if f"'{_PLACEHOLDER}'" in text or f'"{_PLACEHOLDER}"' in text:
            return [f"{path}: __BCRYPT_PLACEHOLDER__ literal without documented password in SQL comment"]
        return errors

    if f"'{_PLACEHOLDER}'" in text or f'"{_PLACEHOLDER}"' in text:
        password = documented_password(text)
        if password:
            return []  # pipeline runs materialize_seed_passwords.py after RDS apply
        return [f"{path}: __BCRYPT_PLACEHOLDER__ literal without documented password in SQL comment"]

    password = documented_password(text)
    if not password:
        return errors

    hashes = bcrypt_hashes(text)
    if not hashes:
        errors.append(f"{path}: documents password but contains no bcrypt hashes")
        return errors

    for digest in hashes:
        try:
            ok = bcrypt.checkpw(password.encode("utf-8"), digest.encode("utf-8"))
        except ValueError as exc:
            errors.append(f"{path}: invalid bcrypt hash ({exc})")
            continue
        if not ok:
            errors.append(
                f"{path}: bcrypt hash does not match documented dev password "
                f"(RDS login fails; pytest may still pass via conftest fixtures)"
            )
            break
    return errors


def _parse_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def verify_rds_seed_password(
    target_app: str,
    repo_root: Path | None = None,
) -> list[str]:
    """Check one seed user on RDS: hash present, starts with $2, matches documented password."""
    from _shared.pipeline_context import target_app_root_rel

    root = repo_root or _REPO_ROOT
    app_dir = root / target_app_root_rel(target_app)
    if not (app_dir / "db").is_dir():
        app_dir = root / "target-apps" / target_app

    from _shared.rds_env import connection_url, load_target_app_env, schema_for_app
    from _shared.seed_credentials import collect_credentials

    load_target_app_env(target_app, root)
    creds = collect_credentials(app_dir)
    if not creds:
        return []

    lookup_value, password, lookup_col, hash_col = creds[0]
    seed_path = None
    sql_dir = app_dir / "db" / "sql"
    for path in sorted(sql_dir.glob("*seed*.sql")):
        if "fix" not in path.name.lower():
            seed_path = path
            break

    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        return ["RDS seed check skipped: sqlalchemy not installed"]

    schema = schema_for_app(target_app)

    try:
        # SQLAlchemy defaults a bare "postgresql://" URL to the psycopg2 driver, which
        # isn't installed anywhere in this repo (only psycopg 3.x is) — force the psycopg
        # dialect so this matches the psycopg.connect() calls used elsewhere for RDS.
        sqlalchemy_url = connection_url().replace("postgresql://", "postgresql+psycopg://", 1)
        engine = create_engine(sqlalchemy_url, pool_pre_ping=True)
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT {hash_col} FROM {schema}.users "
                    f"WHERE {lookup_col} = :lookup LIMIT 1"
                ),
                {"lookup": lookup_value},
            ).fetchone()
    except Exception as exc:
        return [f"RDS seed check failed (connection/query): {exc}"]

    if not row:
        return [
            f"RDS: seed user '{lookup_value}' not found in {schema}.users — "
            "run apply_sql_to_rds.py"
        ]

    stored = row[0]
    if not isinstance(stored, str) or not stored.startswith("$2"):
        return [
            f"RDS: {hash_col} for '{lookup_value}' is not a valid bcrypt hash — "
            "run apply_sql_to_rds.py (auto-materializes passwords) or "
            "python agents/_shared/materialize_seed_passwords.py --target-app "
            f"{target_app}"
        ]

    try:
        if not bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8")):
            name = seed_path.name if seed_path else "seed SQL"
            return [
                f"RDS: {hash_col} for '{lookup_value}' does not match documented password "
                f"({name}) — README login will 401"
            ]
    except ValueError as exc:
        return [f"RDS: invalid bcrypt hash for '{lookup_value}': {exc}"]

    return []


def verify_target_app(
    target_app: str,
    repo_root: Path | None = None,
    *,
    check_rds: bool = False,
) -> list[str]:
    from _shared.pipeline_context import target_app_root_rel

    root = repo_root or _REPO_ROOT
    sql_dir = root / target_app_root_rel(target_app) / "db" / "sql"
    if not sql_dir.is_dir():
        sql_dir = root / "target-apps" / target_app / "db" / "sql"
    errors: list[str] = []

    if sql_dir.is_dir():
        for path in sorted(sql_dir.glob("*.sql")):
            errors.extend(scan_sql_antipatterns(path))
        for path in sorted(sql_dir.glob("*seed*.sql")):
            if "fix" in path.name.lower():
                continue  # repair scripts; primary seed file is source of truth
            errors.extend(verify_seed_file(path))

    if check_rds:
        errors.extend(verify_rds_seed_password(target_app, root))

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify seed SQL bcrypt hashes")
    parser.add_argument("--target-app", required=True)
    parser.add_argument("--repo-root", default=str(_REPO_ROOT))
    parser.add_argument(
        "--check-rds",
        action="store_true",
        help="Also verify stored hash on RDS (uses .env.local POSTGRES_MCP_* or app .env)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print on failure",
    )
    args = parser.parse_args()

    errors = verify_target_app(
        args.target_app,
        Path(args.repo_root),
        check_rds=args.check_rds,
    )
    # Treat RDS skip messages as non-fatal
    fatal = [e for e in errors if not e.startswith("RDS seed check skipped")]
    if fatal:
        for err in fatal:
            print(err, file=sys.stderr)
        return 1
    for err in errors:
        print(err, file=sys.stderr)
    if not args.quiet:
        print(f"seed bcrypt OK: {args.target_app}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
