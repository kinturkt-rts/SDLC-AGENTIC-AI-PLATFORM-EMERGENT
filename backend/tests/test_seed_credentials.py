"""Tests for seed credential parsing (materialize_seed_passwords dependency)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.seed_credentials import (  # noqa: E402
    collect_credentials,
    hash_column_and_password,
    parse_seed_credentials,
    seed_sql_has_placeholders,
)


def test_parse_email_layout_seed_credentials(tmp_path: Path) -> None:
    seed = tmp_path / "010_seed.sql"
    seed.write_text(
        '-- Password for all seed users: "KnowledgeHub2024!"\n'
        "INSERT INTO users (id, email, display_name, role, hashed_password) VALUES\n"
        "  ('a1000000-0000-0000-0000-000000000001', 'alice@example.com', 'Alice', 'employee', "
        "'__BCRYPT_PLACEHOLDER__');\n",
        encoding="utf-8",
    )
    creds = parse_seed_credentials(seed)
    emails = {row[0] for row in creds}
    assert "alice@example.com" in emails
    assert all(row[1] == "KnowledgeHub2024!" for row in creds)
    assert all(row[2] == "email" and row[3] == "hashed_password" for row in creds)


def test_collect_credentials_training_compliance_still_works() -> None:
    app = _REPO_ROOT / "target-apps" / "training-compliance"
    if not app.is_dir():
        pytest.skip("target-apps/training-compliance not present")
    creds = collect_credentials(app)
    assert len(creds) == 5
    assert creds[0][1] == "TrainingPass123!"


def test_collect_credentials_field_service_username_layout() -> None:
    app = _REPO_ROOT / "target-apps" / "field-service-dispatch"
    if not app.is_dir():
        pytest.skip("target-apps/field-service-dispatch not present")
    creds = collect_credentials(app)
    assert ("dana", "Dispatch123!", "username", "hashed_password") in creds


def test_seed_placeholder_gate_covers_non_users_tables(tmp_path: Path) -> None:
    """legal-doc-qa run 1c2fcc05: api_keys.key_hash placeholders must still trip the
    gate that decides whether to run the post-apply RDS safety-net scan. Narrowing
    this to 'looks like a users INSERT' (the old behavior) let non-users placeholders
    skip verification entirely — collect_credentials() staying schema/login-specific
    is fine (it's now just optional credential documentation), but the gate itself
    must not be."""
    app = tmp_path / "api-key-app"
    sql_dir = app / "db" / "sql"
    sql_dir.mkdir(parents=True)
    (sql_dir / "005_seed.sql").write_text(
        "INSERT INTO admin_keys (id, key_hash) VALUES\n"
        "  ('a1000000-0000-0000-0000-000000000001', '__BCRYPT_PLACEHOLDER__');\n",
        encoding="utf-8",
    )

    assert seed_sql_has_placeholders(app) is True
    assert collect_credentials(app) == []


def test_parse_seed_credentials_integer_pk_layout(tmp_path: Path) -> None:
    """database-agent sometimes uses serial/integer PKs instead of UUIDs (fitness-tracker
    run 36445603 hit this: parsing returned zero credentials even though the seed SQL
    correctly documented a password and used __BCRYPT_PLACEHOLDER__)."""
    seed = tmp_path / "005_seed.sql"
    seed.write_text(
        '-- Password for all seed users: "FitnessPass123!"\n'
        "INSERT INTO users (id, username, password_hash, created_at) VALUES\n"
        "    (1, 'alice', '__BCRYPT_PLACEHOLDER__', '2024-01-10 08:00:00+00'),\n"
        "    (2, 'bob',   '__BCRYPT_PLACEHOLDER__', '2024-01-11 09:30:00+00')\n"
        "ON CONFLICT (username) DO NOTHING;\n",
        encoding="utf-8",
    )
    creds = parse_seed_credentials(seed)
    usernames = {row[0] for row in creds}
    assert usernames == {"alice", "bob"}
    assert all(row[1] == "FitnessPass123!" for row in creds)
    assert all(row[2] == "username" and row[3] == "password_hash" for row in creds)


def test_hash_column_and_password_no_login_column(tmp_path: Path) -> None:
    """support-knowledge-hub run 7783adb8: users table has display_name + role but no
    username/email at all. apply_sql_to_rds.py already fills every placeholder with one
    shared hash of the documented password before the INSERT runs (no per-row lookup
    needed) - materialize_seed_passwords.py must recognize that case instead of hard
    failing the whole pipeline over a login column that was never required."""
    app = tmp_path / "support-knowledge-hub"
    sql_dir = app / "db" / "sql"
    sql_dir.mkdir(parents=True)
    (sql_dir / "008_seed.sql").write_text(
        '-- Password for all seed users: "KnowledgeHub2024!"\n'
        "INSERT INTO users (id, display_name, role, hashed_password) VALUES\n"
        "    ('a1b2c3d4-0001-4000-8000-000000000001', 'Alice Chen', 'contributor', '__BCRYPT_PLACEHOLDER__'),\n"
        "    ('a1b2c3d4-0002-4000-8000-000000000002', 'Bob Martinez', 'contributor', '__BCRYPT_PLACEHOLDER__')\n"
        "ON CONFLICT DO NOTHING;\n",
        encoding="utf-8",
    )

    assert seed_sql_has_placeholders(app) is True
    assert collect_credentials(app) == []  # no username/email - nothing to look up per-row
    blanket = hash_column_and_password(app)
    assert blanket == ("hashed_password", "KnowledgeHub2024!")


def test_seed_placeholder_gate_keeps_malformed_user_seed_strict(tmp_path: Path) -> None:
    app = tmp_path / "malformed-user-app"
    sql_dir = app / "db" / "sql"
    sql_dir.mkdir(parents=True)
    (sql_dir / "005_seed.sql").write_text(
        "INSERT INTO users (id, email, hashed_password) VALUES\n"
        "  ('a1000000-0000-0000-0000-000000000001', 'a@example.com', "
        "'__BCRYPT_PLACEHOLDER__');\n",
        encoding="utf-8",
    )

    assert seed_sql_has_placeholders(app) is True
    assert collect_credentials(app) == []
