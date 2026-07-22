"""Tests for SHA-256 API-key seed helpers and SQL validation."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.sha256_api_keys import (  # noqa: E402
    documented_api_keys,
    replace_sha256_placeholders,
    seed_text_has_fake_sha256_tokens,
    sha256_hex,
    validate_seed_sha256_api_keys,
)
from _shared.validate_sql_artifacts import validate_sql_dir  # noqa: E402


def test_replace_labeled_sha256_placeholders() -> None:
    sql = """
-- API key for demo-standard: "demo-standard-key-2024"
-- API key for demo-admin: "demo-admin-key-2024"
INSERT INTO api_keys (key_hash, label) VALUES
  ('__SHA256_PLACEHOLDER:demo-standard__', 'demo-standard'),
  ('__SHA256_PLACEHOLDER:demo-admin__', 'demo-admin');
"""
    out, replaced, errors = replace_sha256_placeholders(sql)
    assert errors == []
    assert replaced == 2
    assert sha256_hex("demo-standard-key-2024") in out
    assert sha256_hex("demo-admin-key-2024") in out
    assert "__SHA256_PLACEHOLDER" not in out


def test_replace_fails_without_api_key_comment() -> None:
    sql = "INSERT INTO api_keys (key_hash) VALUES ('__SHA256_PLACEHOLDER:missing__');"
    out, replaced, errors = replace_sha256_placeholders(sql)
    assert replaced == 0
    assert any("missing" in e for e in errors)
    assert "__SHA256_PLACEHOLDER:missing__" in out


def test_validate_rejects_fake_sha256_tokens(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "011_seed.sql").write_text(
        """
-- Password for all seed API keys: "dev-secret-key-2024!"
INSERT INTO api_keys (id, key_hash, role, label) VALUES
  ('c3000001-0000-0000-0000-000000000001', 'sha256_standard_demo_001', 'standard', 'demo-standard');
""",
        encoding="utf-8",
    )
    errors = validate_seed_sha256_api_keys(sql_dir)
    assert errors
    assert any("sha256_*" in e or "invented" in e for e in errors)
    assert seed_text_has_fake_sha256_tokens(
        (sql_dir / "011_seed.sql").read_text(encoding="utf-8")
    )


def test_validate_accepts_labeled_placeholders_with_comments(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "001_schema.sql").write_text(
        "CREATE TABLE IF NOT EXISTS api_keys (id UUID PRIMARY KEY, key_hash TEXT, label TEXT);",
        encoding="utf-8",
    )
    (sql_dir / "011_seed.sql").write_text(
        """
-- API key for demo-standard: "demo-standard-key-2024"
INSERT INTO api_keys (id, key_hash, label) VALUES
  ('c3000001-0000-0000-0000-000000000001', '__SHA256_PLACEHOLDER:demo-standard__', 'demo-standard');
""",
        encoding="utf-8",
    )
    assert validate_seed_sha256_api_keys(sql_dir) == []
    # Full validate_sql_dir should also pass (no fake tokens)
    assert validate_sql_dir(sql_dir) == []


def test_documented_api_keys_parse() -> None:
    text = '-- API key for demo-admin: "demo-admin-key-2024"\n'
    assert documented_api_keys(text) == {"demo-admin": "demo-admin-key-2024"}
