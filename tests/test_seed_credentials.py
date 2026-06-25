"""Tests for seed credential parsing (materialize_seed_passwords dependency)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.seed_credentials import collect_credentials, parse_seed_credentials  # noqa: E402


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
