"""Tests for agents/_shared/validate_sql_artifacts.py."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.validate_sql_artifacts import (  # noqa: E402
    check_seed_schema_nullability,
    check_uuid_literals,
    parse_seed_inserts,
    validate_sql_dir,
)


def test_gitlab_pipeline_smoke_seed_nullable_ends_at_passes() -> None:
    sql_dir = _REPO_ROOT / "target-apps" / "gitlab-pipeline-smoke" / "db" / "sql"
    assert validate_sql_dir(sql_dir) == []


def test_detects_null_in_not_null_column(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "001_schema.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS app.notices (
            id UUID PRIMARY KEY,
            ends_at TIMESTAMPTZ NOT NULL
        );
        """,
        encoding="utf-8",
    )
    (sql_dir / "002_seed.sql").write_text(
        """
        INSERT INTO app.notices (id, ends_at) VALUES
            ('a1000000-0000-4000-8000-000000000001', NULL);
        """,
        encoding="utf-8",
    )
    errors = check_seed_schema_nullability(sql_dir)
    assert len(errors) == 1
    assert "ends_at" in errors[0]
    assert "NOT NULL" in errors[0]


def test_parses_multiline_insert_with_null(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "001_schema.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS gitlab_pipeline_smoke.notices (
            id UUID PRIMARY KEY,
            ends_at TIMESTAMPTZ
        );
        """,
        encoding="utf-8",
    )
    (sql_dir / "002_seed.sql").write_text(
        """
        INSERT INTO gitlab_pipeline_smoke.notices (id, ends_at) VALUES
            ('b1000000-0000-4000-8000-000000000005', NULL)
        ON CONFLICT (id) DO NOTHING;
        """,
        encoding="utf-8",
    )
    inserts = parse_seed_inserts(sql_dir)
    assert len(inserts) == 1
    assert inserts[0].values[1] is None
    assert check_seed_schema_nullability(sql_dir) == []


def test_check_uuid_literals_rejects_non_hex(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "008_seed.sql").write_text(
        """\
INSERT INTO runbooks (id, title) VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'ok hex a'),
    ('11111111-1111-1111-1111-111111111111', 'ok hex 1'),
    ('gggggggg-gggg-gggg-gggg-gggggggggggg', 'bad g'),
    ('iiiiiiii-iiii-iiii-iiii-iiiiiiiiiiii', 'bad i'),
    ('ffffffff-ffff-ffff-ffff-ffffffffffff', 'ok hex f');
""",
        encoding="utf-8",
    )
    errors = check_uuid_literals(sql_dir)
    assert len(errors) == 2
    assert any("gggggggg" in e and "g" in e for e in errors)
    assert any("iiiiiiii" in e and "i" in e for e in errors)


def test_check_uuid_literals_passes_valid_hex(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "008_seed.sql").write_text(
        """\
INSERT INTO t (id, name) VALUES
    ('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'realistic'),
    ('00000001-0000-0000-0000-000000000001', 'counter style');
""",
        encoding="utf-8",
    )
    assert check_uuid_literals(sql_dir) == []


def test_validate_sql_dir_catches_bad_uuids(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "001_schema.sql").write_text(
        "CREATE TABLE IF NOT EXISTS t (id UUID PRIMARY KEY, name TEXT NOT NULL);",
        encoding="utf-8",
    )
    (sql_dir / "010_seed.sql").write_text(
        """\
INSERT INTO t (id, name) VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'ok'),
    ('hhhhhhhh-hhhh-hhhh-hhhh-hhhhhhhhhhhh', 'bad');
""",
        encoding="utf-8",
    )
    errors = validate_sql_dir(sql_dir)
    assert len(errors) == 1
    assert "hhhhhhhh" in errors[0]
