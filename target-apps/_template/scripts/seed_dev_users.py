"""Replace bcrypt placeholders in the seed with real hashes.

The database-agent ships seed SQL with `'__BCRYPT_PLACEHOLDER__'` in every
`password_hash` column. The LLM cannot compute real bcrypt hashes, so the
developer-agent scaffolds this script: it reads the credential mapping below,
hashes each plaintext with bcrypt at deploy time, and UPDATEs the placeholder
rows in the live database.

Usage:
    # After running migrations + seed SQL against the target DB:
    python scripts/seed_dev_users.py

Required environment:
    DATABASE_URL  — same DSN the app uses (postgresql+psycopg://... or sqlite:///)

The developer-agent overwrites `_CREDENTIALS` below with the exact mapping from
the database-agent's HANDOFF.md `### seedCredentials` table. Do not hand-edit
the rest of this file unless the bcrypt API changes.
"""

from __future__ import annotations

import os
import sys

try:
    import bcrypt
except ImportError:
    print("bcrypt not installed. Run: pip install bcrypt>=4.0", file=sys.stderr)
    raise SystemExit(1)

try:
    from sqlalchemy import create_engine, text
except ImportError:
    print("SQLAlchemy not installed. Run: pip install sqlalchemy", file=sys.stderr)
    raise SystemExit(1)


# ── Developer-agent OVERWRITES this constant from HANDOFF.md seedCredentials ──
# Format: ("username_or_email_column_value", "plaintext_password")
# The script does NOT log plaintext passwords beyond the count below.
_CREDENTIALS: list[tuple[str, str]] = [
    # Example (delete and replace with real entries from HANDOFF.md):
    # ("priya@example.com", "AuditPass123!"),
]

# ── Which column to look up users by — usually "email" or "username" ──────────
_LOOKUP_COLUMN = "email"

# ── Table name (defaults match the golden template) ───────────────────────────
_USERS_TABLE = "users"
_HASH_COLUMN = "password_hash"
_PLACEHOLDER = "__BCRYPT_PLACEHOLDER__"


def _bcrypt_hash(plaintext: str) -> str:
    """Compute a bcrypt hash with default cost. Returns a str (utf-8 decoded)."""
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def main() -> int:
    if not _CREDENTIALS:
        print(
            "No credentials configured in _CREDENTIALS. Edit this file with the "
            "(lookup_value, plaintext) pairs from HANDOFF.md seedCredentials.",
            file=sys.stderr,
        )
        return 1

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not set. Export it or load .env first.", file=sys.stderr)
        return 1

    engine = create_engine(database_url, future=True)
    updated = 0
    skipped = 0

    with engine.begin() as conn:
        for lookup_value, plaintext in _CREDENTIALS:
            hashed = _bcrypt_hash(plaintext)
            result = conn.execute(
                text(
                    f"UPDATE {_USERS_TABLE} "
                    f"SET {_HASH_COLUMN} = :hashed "
                    f"WHERE {_LOOKUP_COLUMN} = :lookup "
                    f"  AND {_HASH_COLUMN} = :placeholder"
                ),
                {"hashed": hashed, "lookup": lookup_value, "placeholder": _PLACEHOLDER},
            )
            if result.rowcount > 0:
                updated += result.rowcount
            else:
                skipped += 1
                print(
                    f"  skipped: no row found with {_LOOKUP_COLUMN}={lookup_value!r} "
                    f"and {_HASH_COLUMN}={_PLACEHOLDER!r} "
                    "(already seeded, wrong env, or user missing)",
                    file=sys.stderr,
                )

    print(f"seed_dev_users.py: updated {updated} rows, skipped {skipped}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
