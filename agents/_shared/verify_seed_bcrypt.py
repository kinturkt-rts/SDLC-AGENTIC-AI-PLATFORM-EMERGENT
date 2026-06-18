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

# e.g. Password for all seed users: "AuditPass123!"  OR  all passwords are "Password1!"
_PASSWORD_COMMENT_RE = re.compile(
    r'(?:Password|passwords?)[^"\n]*"([^"]+)"',
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


def documented_password(seed_text: str) -> str | None:
    match = _PASSWORD_COMMENT_RE.search(seed_text)
    return match.group(1) if match else None


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
    root = repo_root or _REPO_ROOT
    app_dir = root / "target-apps" / target_app
    sql_dir = app_dir / "db" / "sql"
    if not sql_dir.is_dir():
        return []

    seed_path: Path | None = None
    password: str | None = None
    username: str | None = None
    for path in sorted(sql_dir.glob("*seed*.sql")):
        text = path.read_text(encoding="utf-8")
        pw = documented_password(text)
        user = first_seed_username(text)
        if pw and user:
            seed_path = path
            password = pw
            username = user
            break
    if not seed_path or not password or not username:
        return []

    env = _parse_dotenv(app_dir / ".env")
    db_url = env.get("DATABASE_URL") or os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        return [
            f"RDS seed check skipped: no DATABASE_URL in target-apps/{target_app}/.env "
            "(copy .env.example after pipeline; re-run with --check-rds)"
        ]

    schema = env.get("POSTGRES_SCHEMA") or target_app.replace("-", "_")

    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        return ["RDS seed check skipped: sqlalchemy not installed"]

    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT password_hash FROM {schema}.users "
                    "WHERE username = :username LIMIT 1"
                ),
                {"username": username},
            ).fetchone()
    except Exception as exc:
        return [f"RDS seed check failed (connection/query): {exc}"]

    if not row:
        return [
            f"RDS: seed user '{username}' not found in {schema}.users — "
            "run apply_sql_to_rds.py"
        ]

    stored = row[0]
    if not isinstance(stored, str) or not stored.startswith("$2"):
        return [
            f"RDS: password_hash for '{username}' is corrupt (missing leading '$') — "
            "likely dollar-quoted SQL; use single quotes in seed/fix migrations"
        ]

    try:
        if not bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8")):
            return [
                f"RDS: password_hash for '{username}' does not match seed SQL password "
                f"(documented in {seed_path.name}) — README login will 401"
            ]
    except ValueError as exc:
        return [f"RDS: invalid bcrypt hash for '{username}': {exc}"]

    return []


def verify_target_app(
    target_app: str,
    repo_root: Path | None = None,
    *,
    check_rds: bool = False,
) -> list[str]:
    root = repo_root or _REPO_ROOT
    sql_dir = root / "target-apps" / target_app / "db" / "sql"
    errors: list[str] = []

    if sql_dir.is_dir():
        for path in sorted(sql_dir.glob("*.sql")):
            errors.extend(scan_sql_antipatterns(path))
        for path in sorted(sql_dir.glob("*seed*.sql")):
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
        help="Also verify stored hash on RDS (needs target-apps/<app>/.env DATABASE_URL)",
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
    print(f"seed bcrypt OK: {args.target_app}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
