"""Parse seed SQL / HANDOFF for dev login credentials (shared by materialize + verify)."""

from __future__ import annotations

import re
from pathlib import Path

from _shared.verify_seed_bcrypt import documented_password, first_seed_username

_PLACEHOLDER = "__BCRYPT_PLACEHOLDER__"
_SEED_CREDENTIALS_HEADER = re.compile(r"^###\s*seedCredentials\s*$", re.MULTILINE | re.IGNORECASE)
_USER_INSERT_USERNAME = re.compile(
    r"\('[0-9a-f-]{36}',\s*'([^']+)',\s*'(?:__BCRYPT_PLACEHOLDER__|\$2[aby]\$12\$[^']*)'",
    re.IGNORECASE,
)
_USER_INSERT_EMAIL = re.compile(
    r"\('[0-9a-f-]{36}',\s*'[0-9a-f-]{36}',\s*'([^']+@[^']+)',\s*'(?:__BCRYPT_PLACEHOLDER__|\$2[aby]\$12\$[^']*)'",
    re.IGNORECASE,
)


def users_table_layout(seed_path: Path) -> tuple[str, str] | None:
    text = seed_path.read_text(encoding="utf-8")
    header = re.search(
        r"INSERT\s+INTO\s+(?:\S+\.)?users\s*\(([^)]+)\)",  # schema prefix optional (SET search_path style)
        text,
        re.IGNORECASE,
    )
    if not header:
        return None
    cols = [c.strip().strip('"') for c in header.group(1).split(",")]
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
            hash_col = "hashed_password" if "@" in lookup else "password_hash"
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
        # Override hash_col from the actual seed SQL — parse_handoff_credentials guesses
        # "password_hash" for username apps but many apps use "hashed_password" instead.
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
    sql_dir = app_dir / "db" / "sql"
    if not sql_dir.is_dir():
        return False
    for seed in sorted(sql_dir.glob("*seed*.sql")):
        if "fix" in seed.name.lower():
            continue
        text = seed.read_text(encoding="utf-8")
        if f"'{_PLACEHOLDER}'" in text or f'"{_PLACEHOLDER}"' in text:
            return True
    return False
