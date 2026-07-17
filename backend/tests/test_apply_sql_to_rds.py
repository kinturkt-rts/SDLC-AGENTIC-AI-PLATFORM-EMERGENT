"""Tests for apply_sql_to_rds schema resolution."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "apply_sql_to_rds.py"


def _load_module():
    sys.modules.pop("apply_sql_to_rds", None)
    spec = importlib.util.spec_from_file_location("apply_sql_to_rds", _SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["apply_sql_to_rds"] = module
    spec.loader.exec_module(module)
    return module


def test_resolve_app_schema_from_target_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POSTGRES_APP_SCHEMA", raising=False)
    mod = _load_module()
    assert mod.resolve_app_schema("meeting-assistant") == "meeting_assistant"


def test_resolve_app_schema_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_APP_SCHEMA", "custom_schema")
    mod = _load_module()
    assert mod.resolve_app_schema("meeting-assistant") == "custom_schema"


def test_split_sql_statements_ignores_semicolon_inside_string() -> None:
    mod = _load_module()
    sql = "INSERT INTO t (c) VALUES ('a; b'); SELECT 1;"
    parts = mod.split_sql_statements(sql)
    assert len(parts) == 2
    assert "a; b" in parts[0]
    assert parts[1] == "SELECT 1"


def test_resolve_host_port_prefers_postgres_mcp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_MCP_DB_ENDPOINT", "mydb.example.rds.amazonaws.com")
    monkeypatch.setenv("POSTGRES_MCP_PORT", "5433")
    mod = _load_module()
    host, port = mod._resolve_host_port("postgresql://ignored")
    assert host == "mydb.example.rds.amazonaws.com"
    assert port == 5433


def test_resolve_host_port_parses_url_when_password_contains_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POSTGRES_MCP_DB_ENDPOINT", raising=False)
    mod = _load_module()
    url = (
        "postgresql://postgres:MyPass@Database_26@"
        "agenticaidbinstance.c1u0cggiolxp.us-east-2.rds.amazonaws.com:5432/sdlc?sslmode=require"
    )
    host, port = mod._resolve_host_port(url)
    assert host == "agenticaidbinstance.c1u0cggiolxp.us-east-2.rds.amazonaws.com"
    assert port == 5432


def test_sql_files_need_pgvector_detects_vector_column(tmp_path: Path) -> None:
    mod = _load_module()
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "003_create_bugs.sql").write_text(
        "CREATE TABLE bugs (embedding vector(1536));",
        encoding="utf-8",
    )
    assert mod._sql_files_need_pgvector([sql_dir / "003_create_bugs.sql"]) is True


def test_sql_files_need_pgvector_false_for_plain_tables(tmp_path: Path) -> None:
    mod = _load_module()
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "002_create_users.sql").write_text(
        "CREATE TABLE users (id uuid primary key);",
        encoding="utf-8",
    )
    assert mod._sql_files_need_pgvector([sql_dir / "002_create_users.sql"]) is False


def test_sql_files_need_pgtrgm_detects_trigram_index(tmp_path: Path) -> None:
    mod = _load_module()
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "003_add_indexes.sql").write_text(
        "CREATE INDEX idx_recipes_name ON recipes USING gin (name gin_trgm_ops);",
        encoding="utf-8",
    )
    assert mod._sql_files_need_pgtrgm([sql_dir / "003_add_indexes.sql"]) is True


def test_ensure_pgtrgm_relocates_extension_to_public() -> None:
    mod = _load_module()

    class FakeCursor:
        schemas = iter(["old_app_schema", "public"])

        def __init__(self) -> None:
            self.executed: list[str] = []

        def execute(self, stmt: str) -> None:
            self.executed.append(str(stmt))

        def fetchone(self) -> tuple[str] | None:
            return (next(self.schemas),)

    cur = FakeCursor()
    mod._ensure_pgtrgm_extension(cur, verbose=False)

    assert "ALTER EXTENSION pg_trgm SET SCHEMA public" in cur.executed


def test_connection_url_prefers_postgres_mcp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://bad:pass@word@host:5432/db")
    monkeypatch.setenv("POSTGRES_MCP_DB_ENDPOINT", "host.example.com")
    monkeypatch.setenv("POSTGRES_MCP_DATABASE", "sdlc_agentic_ai")
    monkeypatch.setenv("POSTGRES_MCP_DB_USER", "postgres")
    monkeypatch.setenv("POSTGRES_MCP_DB_PASSWORD", "MyPass@Database_26")
    monkeypatch.setenv("POSTGRES_MCP_PORT", "5432")
    mod = _load_module()
    url = mod._connection_url()
    assert "MyPass%40Database_26" in url
    assert "host.example.com:5432/sdlc_agentic_ai" in url


def test_preprocess_seed_sql_gives_each_occurrence_a_distinct_hash() -> None:
    """Regression: legal-doc-qa run 1c2fcc05 seeded 5 api_keys rows, each with
    __BCRYPT_PLACEHOLDER__ for key_hash (UNIQUE NOT NULL). A single shared digest
    reused across all 5 rows collided on the UNIQUE constraint and the whole INSERT
    failed. Each occurrence must get its own freshly-salted hash."""
    import bcrypt

    mod = _load_module()
    sql = (
        '-- Password for all seed API keys: "LegalQA2024!"\n'
        "INSERT INTO api_keys (id, key_hash, role) VALUES\n"
        "    (1, '__BCRYPT_PLACEHOLDER__', 'legal_ops'),\n"
        "    (2, '__BCRYPT_PLACEHOLDER__', 'reader'),\n"
        "    (3, '__BCRYPT_PLACEHOLDER__', 'reader');\n"
    )
    result = mod._preprocess_seed_sql(sql)

    assert "__BCRYPT_PLACEHOLDER__" not in result
    hashes = re.findall(r"'(\$2[aby]\$12\$[./A-Za-z0-9]{53})'", result)
    assert len(hashes) == 3
    assert len(set(hashes)) == 3, "each occurrence must get a distinct hash (UNIQUE columns)"
    for digest in hashes:
        assert bcrypt.checkpw(b"LegalQA2024!", digest.encode("utf-8"))
