#!/usr/bin/env python3
"""Seed dev users — updates password_hash for seed users.

Run AFTER applying migrations + seed SQL:
    python scripts/seed_dev_users.py

This script ensures all seed users have valid bcrypt hashes for the
documented dev password (AssetPass123!).
"""
from __future__ import annotations

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from sqlalchemy import create_engine, text

# Dev credentials — matches 011_seed.sql users
_CREDENTIALS = [
    ("kevin_admin", "AssetPass123!"),
    ("sarah_staff", "AssetPass123!"),
    ("mike_staff", "AssetPass123!"),
    ("dana_finance", "AssetPass123!"),
]


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv()

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL not set. Copy .env.example to .env first.")
        sys.exit(1)

    schema = os.environ.get("POSTGRES_SCHEMA", "it_asset_lifecycle")
    engine = create_engine(url)

    with engine.begin() as conn:
        conn.execute(text(f"SET search_path TO {schema}, public"))
        for username, password in _CREDENTIALS:
            hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
            result = conn.execute(
                text("UPDATE users SET password_hash = :hash WHERE username = :user"),
                {"hash": hashed, "user": username},
            )
            print(f"  Updated {username}: {result.rowcount} row(s)")

    print("Done — seed users now have valid bcrypt hashes.")


if __name__ == "__main__":
    main()
