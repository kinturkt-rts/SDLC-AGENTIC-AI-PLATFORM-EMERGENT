"""Tests for seed bcrypt verification helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import bcrypt

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.verify_seed_bcrypt import (  # noqa: E402
    scan_sql_antipatterns,
    verify_seed_file,
)

_GOOD_HASH = bcrypt.hashpw(b"TestPass1!", bcrypt.gensalt(rounds=12)).decode()


def test_verify_seed_file_accepts_matching_hash(tmp_path: Path) -> None:
    seed = tmp_path / "009_seed.sql"
    seed.write_text(
        '-- Password for all seed users: "TestPass1!"\n'
        f"INSERT INTO users (username, password_hash) VALUES ('u1', '{_GOOD_HASH}');\n",
        encoding="utf-8",
    )
    assert verify_seed_file(seed) == []


def test_verify_seed_file_rejects_placeholder(tmp_path: Path) -> None:
    seed = tmp_path / "009_seed.sql"
    seed.write_text(
        '-- Password for all seed users: "TestPass1!"\n'
        "INSERT INTO users (username, password_hash) VALUES ('u1', '$2b$12$LJ3m4ys3Lz0QmXE7U5CvYOFNGrMjK2G0zVQ8Wk3vWJp4lZDoIS5cS');\n",
        encoding="utf-8",
    )
    errors = verify_seed_file(seed)
    assert len(errors) == 1
    assert "does not match" in errors[0]


def test_scan_rejects_dollar_quoted_bcrypt(tmp_path: Path) -> None:
    fix = tmp_path / "010_fix.sql"
    fix.write_text(
        "UPDATE users SET password_hash = $pwd$2b$12$abcdefghijklmnopQRSTUVWXYZ012345678901234567890$pwd$;\n",
        encoding="utf-8",
    )
    errors = scan_sql_antipatterns(fix)
    assert len(errors) == 1
    assert "dollar-quoted" in errors[0]


def test_verify_seed_file_skips_api_key_app_without_user_hashes(tmp_path: Path) -> None:
    seed = tmp_path / "004_seed.sql"
    seed.write_text(
        '-- Password for organizer reference only: "NoticeAdmin2024!"\n'
        "INSERT INTO categories (name) VALUES ('General');\n",
        encoding="utf-8",
    )
    assert verify_seed_file(seed) == []


def test_verify_seed_file_accepts_placeholder_in_token_hash_with_password_comment(
    tmp_path: Path,
) -> None:
    """expense-tracker regression: opaque-token seeds use token_hash/key_hash, not
    hashed_password. A documented password comment must still pass SQL verify so
    materialize can replace the literal — do not fail with a false 'no password' error."""
    seed = tmp_path / "008_seed.sql"
    seed.write_text(
        '-- Password for all seed users: "ExpenseTest123!"\n'
        "INSERT INTO users (id, email, role, token_hash) VALUES\n"
        "  ('b1b2c3d4-0001-4000-8000-000000000001', 'admin@example.com', 'admin', "
        "'__BCRYPT_PLACEHOLDER__');\n"
        "INSERT INTO api_keys (id, key_hash, role) VALUES\n"
        "  ('c1b2c3d4-0001-4000-8000-000000000001', '__BCRYPT_PLACEHOLDER__', 'admin');\n",
        encoding="utf-8",
    )
    assert verify_seed_file(seed) == []


def test_verify_seed_file_rejects_placeholder_without_password_comment(tmp_path: Path) -> None:
    seed = tmp_path / "008_seed.sql"
    seed.write_text(
        "INSERT INTO users (email, token_hash) VALUES ('a@example.com', '__BCRYPT_PLACEHOLDER__');\n",
        encoding="utf-8",
    )
    errors = verify_seed_file(seed)
    assert len(errors) == 1
    assert "without documented password" in errors[0]
