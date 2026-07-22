"""Parse seed SQL / HANDOFF for dev login credentials (shared by materialize + verify)."""

from __future__ import annotations

import re
from pathlib import Path

from _shared.verify_seed_bcrypt import documented_password, first_seed_username

_PLACEHOLDER = "__BCRYPT_PLACEHOLDER__"
_SEED_CREDENTIALS_HEADER = re.compile(r"^###\s*seedCredentials\s*$", re.MULTILINE | re.IGNORECASE)

# Users PK is either a UUID string or an auto-increment integer — both are valid
# schema designs database-agent produces; the leading tuple value must match either.
_PK_LITERAL = r"(?:'[0-9a-f-]{36}'|\d+)"
_USER_INSERT_USERNAME = re.compile(
    rf"\(\s*{_PK_LITERAL}\s*,\s*'([^']+)',\s*'(?:__BCRYPT_PLACEHOLDER__|\$2[aby]\$12\$[^']*)'",
    re.IGNORECASE,
)
_USER_INSERT_EMAIL = re.compile(
    rf"\(\s*{_PK_LITERAL}\s*,\s*{_PK_LITERAL}\s*,\s*'([^']+@[^']+)',\s*'(?:__BCRYPT_PLACEHOLDER__|\$2[aby]\$12\$[^']*)'",
    re.IGNORECASE,
)
_USERS_INSERT_HEADER = re.compile(
    r"INSERT\s+INTO\s+(?:\S+\.)?users\s*\(([^)]+)\)",
    re.IGNORECASE,
)
_USERS_INSERT_STATEMENT = re.compile(
    r"INSERT\s+INTO\s+(?:\S+\.)?users\s*"
    r"\((?=[^)]*\b(?:password_hash|hashed_password)\b)[^)]*\)\s*"
    r"VALUES\b(?P<values>.*?)(?:;|$)",
    re.IGNORECASE | re.DOTALL,
)


def _users_insert_columns(seed_path: Path) -> list[str] | None:
    text = seed_path.read_text(encoding="utf-8")
    header = _USERS_INSERT_HEADER.search(text)
    if not header:
        return None
    return [c.strip().strip('"') for c in header.group(1).split(",")]


def _split_sql_tuple_values(inner: str) -> list[str | None]:
    """Split comma-separated SQL literals inside a VALUES tuple."""
    values: list[str | None] = []
    i = 0
    n = len(inner)
    while i < n:
        while i < n and inner[i] in " \t\n\r,":
            i += 1
        if i >= n:
            break
        if inner[i] == "'":
            i += 1
            buf: list[str] = []
            while i < n:
                if inner[i] == "'":
                    if i + 1 < n and inner[i + 1] == "'":
                        buf.append("'")
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    buf.append(inner[i])
                    i += 1
            values.append("".join(buf))
            continue
        if inner[i : i + 4].upper() == "NULL":
            values.append(None)
            i += 4
            continue
        start = i
        while i < n and inner[i] != ",":
            i += 1
        values.append(inner[start:i].strip())
    return values


def _parse_users_insert_rows(
    seed_path: Path,
    *,
    lookup_col: str,
    hash_col: str,
) -> list[str]:
    """Column-aware extraction of email/username from users INSERT rows."""
    text = seed_path.read_text(encoding="utf-8")
    cols = _users_insert_columns(seed_path)
    if not cols:
        return []
    try:
        lookup_idx = cols.index(lookup_col)
        hash_idx = cols.index(hash_col)
    except ValueError:
        return []

    lookups: list[str] = []
    in_users_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if _USERS_INSERT_HEADER.search(stripped):
            in_users_block = True
            continue
        if not in_users_block:
            continue
        if stripped.startswith("ON CONFLICT") or (
            stripped.startswith("--") and not stripped.startswith("('")
        ):
            in_users_block = False
            continue
        if not stripped.startswith("("):
            if stripped and not stripped.startswith("--"):
                in_users_block = False
            continue
        tuple_match = re.search(r"\((.+)\)\s*(?:,|;)?\s*$", stripped)
        if not tuple_match:
            continue
        vals = _split_sql_tuple_values(tuple_match.group(1))
        if len(vals) <= max(lookup_idx, hash_idx):
            continue
        hash_val = vals[hash_idx]
        lookup_val = vals[lookup_idx]
        if not lookup_val or not hash_val:
            continue
        if hash_val == _PLACEHOLDER or hash_val.startswith("$2"):
            lookups.append(lookup_val)
    return lookups


def users_table_layout(seed_path: Path) -> tuple[str, str] | None:
    cols = _users_insert_columns(seed_path)
    if not cols:
        return None
    hash_col = next(
        (c for c in cols if c in ("password_hash", "hashed_password")),
        None,
    )
    if not hash_col:
        return None
    if "email" in cols:
        return "email", hash_col
    if "username" in cols:
        return "username", hash_col
    return None


def hash_column_and_password(app_dir: Path) -> tuple[str, str] | None:
    """Resolve (hash_col, documented_password) without requiring a username/email column.

    Some database-agent schemas seed a users table with a password hash but no
    login-identifying column (e.g. just ``display_name`` + ``role``) — there is no
    per-row lookup key, but apply_sql_to_rds.py's own pre-apply preprocessing already
    fills every ``__BCRYPT_PLACEHOLDER__`` with one shared hash of the documented
    password (same assumption: all seed users share one dev password). This lets
    materialize_seed_passwords.py recognize that case as already-materialized (or
    blanket-fixable) instead of hard-failing the whole pipeline over a missing column
    it never actually needed.
    """
    sql_dir = app_dir / "db" / "sql"
    if not sql_dir.is_dir():
        return None
    for seed in sorted(sql_dir.glob("*seed*.sql")):
        if "fix" in seed.name.lower():
            continue
        cols = _users_insert_columns(seed)
        if not cols:
            continue
        hash_col = next((c for c in cols if c in ("password_hash", "hashed_password")), None)
        if not hash_col:
            continue
        password = documented_password(seed.read_text(encoding="utf-8"))
        if password:
            return hash_col, password
    return None


def parse_handoff_credentials(handoff_path: Path) -> list[tuple[str, str, str, str]]:
    if not handoff_path.is_file():
        return []
    text = handoff_path.read_text(encoding="utf-8")
    if not _SEED_CREDENTIALS_HEADER.search(text):
        return []
    start = _SEED_CREDENTIALS_HEADER.search(text).end()
    block = text[start : start + 4000]
    rows: list[tuple[str, str, str, str]] = []
    for line in block.splitlines():
        if not line.strip().startswith("|"):
            break
        if "username" in line.lower() and "password" in line.lower():
            continue
        if re.match(r"^\|\s*[-:]+\s*\|", line):
            continue
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) >= 3 and parts[0] and parts[2]:
            lookup = parts[0]
            lookup_col = "email" if "@" in lookup else "username"
            hash_col = "hashed_password"
            rows.append((lookup, parts[2], lookup_col, hash_col))
    return rows


def parse_seed_credentials(seed_path: Path) -> list[tuple[str, str, str, str]]:
    text = seed_path.read_text(encoding="utf-8")
    password = documented_password(text)
    if not password:
        return []
    layout = users_table_layout(seed_path)
    if not layout:
        return []
    lookup_col, hash_col = layout
    lookups = _parse_users_insert_rows(
        seed_path, lookup_col=lookup_col, hash_col=hash_col
    )
    if not lookups:
        if lookup_col == "email":
            lookups = _USER_INSERT_EMAIL.findall(text)
        else:
            lookups = _USER_INSERT_USERNAME.findall(text)
            if not lookups:
                user = first_seed_username(text)
                if user:
                    lookups = [user]
    return [(u, password, lookup_col, hash_col) for u in lookups]


def collect_credentials(app_dir: Path) -> list[tuple[str, str, str, str]]:
    handoff = app_dir / "db" / "HANDOFF.md"
    sql_dir = app_dir / "db" / "sql"
    creds = parse_handoff_credentials(handoff)
    if creds:
        # Override hash_col from the actual seed SQL — handoff defaults to
        # "hashed_password"; older apps may still use "password_hash".
        if sql_dir.is_dir():
            for seed in sorted(sql_dir.glob("*seed*.sql")):
                if "fix" in seed.name.lower():
                    continue
                layout = users_table_layout(seed)
                if layout:
                    _, actual_hash_col = layout
                    creds = [(lu, pw, lc, actual_hash_col) for lu, pw, lc, _ in creds]
                    break
        return creds
    if not sql_dir.is_dir():
        return []
    for seed in sorted(sql_dir.glob("*seed*.sql")):
        if "fix" in seed.name.lower():
            continue
        creds.extend(parse_seed_credentials(seed))
    return creds


def seed_sql_has_placeholders(app_dir: Path) -> bool:
    """True when any seed file has bcrypt or SHA-256 placeholder tokens (any table).

    Deliberately not scoped to the users table: materialize_seed_passwords.py's
    find_remaining_placeholder_columns() checks every text/varchar column on RDS, so
    the pre-check that decides whether to bother running it must be equally broad —
    narrowing this to "looks like a users INSERT" previously let placeholders in other
    tables (e.g. api_keys.key_hash) skip the post-apply safety-net scan entirely.

    Also true for invented ``sha256_*`` fake digests so materialize can repair them.
    """
    from _shared.sha256_api_keys import seed_sql_has_sha256_work

    sql_dir = app_dir / "db" / "sql"
    if not sql_dir.is_dir():
        return False
    if seed_sql_has_sha256_work(app_dir):
        return True
    for seed in sorted(sql_dir.glob("*seed*.sql")):
        if "fix" in seed.name.lower():
            continue
        text = seed.read_text(encoding="utf-8")
        if _PLACEHOLDER in text:
            return True
    return False
