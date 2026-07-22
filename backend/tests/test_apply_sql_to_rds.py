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


class _FakeInMemoryPostgres:
    """Minimal in-memory Postgres stand-in driving apply_sql_files()'s auto-heal path.

    Understands just enough SQL to exercise DROP/CREATE SCHEMA, CREATE TABLE IF NOT
    EXISTS (via the real DDL column parser), and the single-column information_schema
    lookup check_ddl_column_drift issues. Anything else (SET search_path, INSERT, etc.)
    is accepted and ignored.
    """

    def __init__(self) -> None:
        self.schemas: dict[str, dict[str, set[str]]] = {}
        self._last_rows: list[tuple[str]] = []

    def execute(self, query: object, params: tuple[str, str] | None = None) -> None:
        from _shared.validate_sql_artifacts import _parse_create_table_columns

        # psycopg's sql.Composed has no __str__ rendering without a live connection —
        # str() falls back to repr(), e.g. "Composed([SQL('DROP SCHEMA IF EXISTS '),
        # Identifier('contacts_api'), SQL(' CASCADE')])". Pull the identifier out of that.
        stmt = str(query)
        upper = stmt.upper().strip()
        identifier_match = re.search(r"Identifier\('([^']+)'\)", stmt)
        if "DROP SCHEMA" in upper:
            if identifier_match:
                self.schemas.pop(identifier_match.group(1), None)
            return
        if "CREATE SCHEMA" in upper:
            if identifier_match:
                self.schemas.setdefault(identifier_match.group(1), {})
            return
        if "SEARCH_PATH" in upper:
            return
        if "INFORMATION_SCHEMA.COLUMNS" in upper:
            assert params is not None
            schema, table = params
            cols = self.schemas.get(schema, {}).get(table, set())
            self._last_rows = [(c,) for c in sorted(cols)]
            return
        if upper.startswith("CREATE TABLE"):
            by_table: dict[tuple[str | None, str], set[str]] = {}
            for spec in _parse_create_table_columns(stmt, source="test"):
                by_table.setdefault((spec.schema, spec.table), set()).add(spec.name)
            for (schema, table), cols in by_table.items():
                eff_schema = schema or self._only_schema()
                table_cols = self.schemas.setdefault(eff_schema, {})
                if table not in table_cols:  # IF NOT EXISTS: no-op when already present
                    table_cols[table] = cols
            return
        return  # INSERT / other statements — irrelevant to this test

    def _only_schema(self) -> str:
        # DDL in these tests always uses unqualified table names against the single
        # schema apply_sql_files just created/reset — there's only ever one candidate.
        assert len(self.schemas) == 1
        return next(iter(self.schemas))

    def fetchall(self) -> list[tuple[str]]:
        return self._last_rows


class _FakeCursorCM:
    def __init__(self, cursor: _FakeInMemoryPostgres) -> None:
        self._cursor = cursor

    def __enter__(self) -> _FakeInMemoryPostgres:
        return self._cursor

    def __exit__(self, *exc: object) -> bool:
        return False


class _FakeConn:
    def __init__(self, cursor: _FakeInMemoryPostgres) -> None:
        self._cursor = cursor

    def __enter__(self) -> "_FakeConn":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def cursor(self) -> _FakeCursorCM:
        return _FakeCursorCM(self._cursor)


def _patch_apply_sql_plumbing(monkeypatch: pytest.MonkeyPatch, mod, db: _FakeInMemoryPostgres) -> None:
    """Bypass AWS/network preflight and real psycopg.connect so apply_sql_files()
    runs entirely against the in-memory fake."""
    import psycopg

    monkeypatch.setattr(mod, "_preflight_aws", lambda **_: True)
    monkeypatch.setattr(mod, "_tcp_probe", lambda *a, **k: (True, "reachable"))
    monkeypatch.setattr(mod, "_resolve_host_port", lambda *_: ("fakehost", 5432))
    monkeypatch.setattr(mod, "_connection_url", lambda: "postgresql://fake")
    monkeypatch.setattr(mod, "_validate_sql_artifacts", lambda _sql_dir: [])
    monkeypatch.setattr(
        "_shared.validate_sql_artifacts.reconcile_nullability_from_ddl",
        lambda *a, **k: [],
    )
    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: _FakeConn(db))


def test_apply_sql_files_auto_heals_stale_table_from_earlier_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: contacts-api's live departments table was `short_code`/int from an
    earlier generation; CREATE TABLE IF NOT EXISTS silently no-op'd against it and the
    current uuid/`code` design never took effect. apply_sql_files() must now detect
    that drift and self-heal (reset schema + reapply) rather than reporting success."""
    mod = _load_module()
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "001_create_departments.sql").write_text(
        "CREATE TABLE IF NOT EXISTS departments (\n"
        "    id uuid PRIMARY KEY,\n"
        "    name text NOT NULL,\n"
        "    code text UNIQUE NOT NULL\n"
        ");\n",
        encoding="utf-8",
    )

    db = _FakeInMemoryPostgres()
    db.schemas["contacts_api"] = {"departments": {"id", "name", "short_code", "created_at"}}
    _patch_apply_sql_plumbing(monkeypatch, mod, db)

    rc = mod.apply_sql_files(sql_dir, target_app="contacts-api", skip_seed=True, quiet=True)

    assert rc == 0
    assert db.schemas["contacts_api"]["departments"] == {"id", "name", "code"}


def test_apply_sql_files_fails_loudly_when_stale_file_still_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When a stale DDL file for the same table sits alongside the current one, reset
    + reapply reproduces the same drift (whichever file sorts first wins) — this must
    fail loudly with an actionable message, not succeed silently on the wrong schema."""
    mod = _load_module()
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    # Sorts first alphabetically -> wins after every reset, same as the real bug.
    (sql_dir / "001_create_departments_old.sql").write_text(
        "CREATE TABLE IF NOT EXISTS departments (\n"
        "    id integer PRIMARY KEY,\n"
        "    short_code text NOT NULL\n"
        ");\n",
        encoding="utf-8",
    )
    (sql_dir / "002_create_departments_new.sql").write_text(
        "CREATE TABLE IF NOT EXISTS departments (\n"
        "    id uuid PRIMARY KEY,\n"
        "    code text NOT NULL\n"
        ");\n",
        encoding="utf-8",
    )

    db = _FakeInMemoryPostgres()
    db.schemas["contacts_api"] = {"departments": {"id", "short_code"}}
    _patch_apply_sql_plumbing(monkeypatch, mod, db)

    rc = mod.apply_sql_files(sql_dir, target_app="contacts-api", skip_seed=True, quiet=True)

    assert rc == 1
