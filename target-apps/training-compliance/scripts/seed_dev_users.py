"""Replace bcrypt placeholders in the seed with real hashes.

Usage:
    # After running migrations + seed SQL against the target DB:
    python scripts/seed_dev_users.py

Required environment:
    DATABASE_URL  - same DSN the app uses (postgresql+psycopg://...)
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


# ── Credentials from seed SQL (password: "TrainingPass123!" for all) ──────────
_CREDENTIALS: list[tuple[str, str]] = [
    ("marcus.chen@example.com", "TrainingPass123!"),
    ("priya.sharma@example.com", "TrainingPass123!"),
    ("alice.johnson@example.com", "TrainingPass123!"),
    ("david.okonkwo@example.com", "TrainingPass123!"),
    ("bob.williams@example.com", "TrainingPass123!"),
]

_LOOKUP_COLUMN = "email"
_USERS_TABLE = "training_compliance.users"
_HASH_COLUMN = "hashed_password"
_PLACEHOLDER = "__BCRYPT_PLACEHOLDER__"


def _bcrypt_hash(plaintext: str) -> str:
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def main() -> int:
    if not _CREDENTIALS:
        print("No credentials configured.", file=sys.stderr)
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
                    f"  skipped: {lookup_value} (already seeded or not found)",
                    file=sys.stderr,
                )

    print(f"seed_dev_users.py: updated {updated} rows, skipped {skipped}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
