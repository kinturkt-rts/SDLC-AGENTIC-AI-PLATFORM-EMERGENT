"""Tests for agents/_shared/validate_rds_parity.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.validate_rds_parity import (  # noqa: E402
    check_seed_materialize_parseable,
    check_timestamp_orm_schema_parity,
    validate_rds_parity,
)


def test_platform_desk_passes_rds_parity() -> None:
    app = _REPO_ROOT / "target-apps" / "platform-desk"
    if not app.is_dir():
        pytest.skip("target-apps/platform-desk not present")
    assert validate_rds_parity(app) == []


def test_seed_materialize_parseable_for_email_layout(tmp_path: Path) -> None:
    app = tmp_path / "good-app"
    sql_dir = app / "db" / "sql"
    sql_dir.mkdir(parents=True)
    (sql_dir / "010_seed.sql").write_text(
        '-- Password for all seed users: "TestPass1!"\n'
        "INSERT INTO users (id, email, display_name, role, hashed_password) VALUES\n"
        "  ('a1000000-0000-0000-0000-000000000001', 'a@example.com', 'A', 'employee', '__BCRYPT_PLACEHOLDER__');\n",
        encoding="utf-8",
    )
    assert check_seed_materialize_parseable(app) == []


def test_detects_unparseable_seed_placeholders(tmp_path: Path) -> None:
    app = tmp_path / "broken-app"
    sql_dir = app / "db" / "sql"
    sql_dir.mkdir(parents=True)
    (sql_dir / "010_seed.sql").write_text(
        "-- no password comment\n"
        "INSERT INTO users (id, email, hashed_password) VALUES\n"
        "  ('a1000000-0000-0000-0000-000000000001', 'a@example.com', "
        "'__BCRYPT_PLACEHOLDER__');\n",
        encoding="utf-8",
    )
    errors = check_seed_materialize_parseable(app)
    assert len(errors) == 1
    assert "collect_credentials" in errors[0]


def test_ignores_api_key_only_bcrypt_placeholders(tmp_path: Path) -> None:
    app = tmp_path / "api-key-app"
    sql_dir = app / "db" / "sql"
    sql_dir.mkdir(parents=True)
    (sql_dir / "010_seed.sql").write_text(
        "INSERT INTO manager_keys (id, key_hash) VALUES\n"
        "  ('a1000000-0000-0000-0000-000000000001', '__BCRYPT_PLACEHOLDER__');\n",
        encoding="utf-8",
    )

    assert check_seed_materialize_parseable(app) == []


def test_detects_text_orm_with_timestamptz_ddl(tmp_path: Path) -> None:
    app = tmp_path / "ts-app"
    models = app / "app" / "models"
    models.mkdir(parents=True)
    sql_dir = app / "db" / "sql"
    sql_dir.mkdir(parents=True)
    (sql_dir / "002_schema.sql").write_text(
        "CREATE TABLE articles (created_at TIMESTAMPTZ);\n", encoding="utf-8"
    )
    (models / "article.py").write_text(
        "created_at: Mapped[str] = mapped_column(Text)\n", encoding="utf-8"
    )
    errors = check_timestamp_orm_schema_parity(app)
    assert any("Text" in e for e in errors)
