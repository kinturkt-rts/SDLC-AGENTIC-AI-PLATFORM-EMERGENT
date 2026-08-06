"""Tests for agents/_shared/validate_sql_artifacts.py."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.validate_sql_artifacts import (  # noqa: E402
    _parse_create_table_columns,
    check_ddl_column_drift,
    check_no_custom_schema_creation,
    check_seed_conflict_on_ruled_tables,
    check_seed_schema_nullability,
    check_uuid_literals,
    check_vector_literal_format,
    parse_seed_inserts,
    split_sql_statements,
    validate_sql_dir,
)


class _FakeCursor:
    """Stubs information_schema.columns lookups for check_ddl_column_drift tests."""

    def __init__(self, live_columns: dict[tuple[str, str], list[str]]) -> None:
        self._live_columns = live_columns
        self._last_result: list[tuple[str]] = []

    def execute(self, _query: str, params: tuple[str, str]) -> None:
        schema, table = params
        cols = self._live_columns.get((schema, table), [])
        self._last_result = [(c,) for c in cols]

    def fetchall(self) -> list[tuple[str]]:
        return self._last_result


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


def test_check_no_custom_schema_creation_rejects_thematic_schema(tmp_path: Path) -> None:
    """Regression for run 4d6e642f-de01-4181-8483-fb1779e33211 (museum-api): database-agent
    created its own "museum" schema instead of relying on apply_sql_to_rds.py's app-slug
    schema ("museum_api") - RDS apply succeeded, but verify_seed_bcrypt.py then failed with
    a false 'relation "museum_api.users" does not exist'."""
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "001_create_schemas.sql").write_text(
        """\
CREATE SCHEMA IF NOT EXISTS museum;
CREATE SCHEMA IF NOT EXISTS audit;
""",
        encoding="utf-8",
    )
    errors = check_no_custom_schema_creation(sql_dir)
    assert len(errors) == 2
    assert any("'museum'" in e for e in errors)
    assert any("'audit'" in e for e in errors)


def test_check_no_custom_schema_creation_passes_when_absent(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "002_users.sql").write_text(
        "CREATE TABLE IF NOT EXISTS users (id UUID PRIMARY KEY);\n",
        encoding="utf-8",
    )
    assert check_no_custom_schema_creation(sql_dir) == []


def test_check_vector_literal_format_rejects_array_to_string(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "010_seed.sql").write_text(
        """\
INSERT INTO chunks (id, embedding) VALUES
    ('d1000000-0000-4000-8000-000000000001',
     (SELECT array_to_string(array_fill(0.01::float, ARRAY[1024]), ','))::vector);
""",
        encoding="utf-8",
    )
    errors = check_vector_literal_format(sql_dir)
    assert len(errors) == 1
    assert "array_to_string" in errors[0]


def test_check_vector_literal_format_rejects_string_agg(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "010_seed.sql").write_text(
        """\
INSERT INTO chunks (id, embedding) VALUES
    ('d1000000-0000-4000-8000-000000000001',
     (SELECT string_agg('0.0', ',') FROM generate_series(1, 1024))::vector);
""",
        encoding="utf-8",
    )
    errors = check_vector_literal_format(sql_dir)
    assert len(errors) == 1
    assert "string_agg" in errors[0]


def test_check_vector_literal_format_passes_array_cast(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "010_seed.sql").write_text(
        """\
INSERT INTO chunks (id, embedding) VALUES
    ('d1000000-0000-4000-8000-000000000001',
     (SELECT array_fill(0.01::real, ARRAY[1024])::vector)),
    ('d1000000-0000-4000-8000-000000000002',
     (SELECT array_agg(0.0)::vector FROM generate_series(1, 1024)));
""",
        encoding="utf-8",
    )
    assert check_vector_literal_format(sql_dir) == []


def test_check_vector_literal_format_ignores_unrelated_array_to_string(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "010_seed.sql").write_text(
        """\
INSERT INTO logs (id, tags) VALUES
    ('d1000000-0000-4000-8000-000000000001', array_to_string(ARRAY['a', 'b'], ','));
""",
        encoding="utf-8",
    )
    assert check_vector_literal_format(sql_dir) == []


def test_check_vector_literal_format_rejects_bare_csv_string_literal(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "010_seed.sql").write_text(
        """\
INSERT INTO chunks (id, embedding) VALUES
    ('d1000000-0000-4000-8000-000000000001', '0.01,0.02,0.03'::vector);
""",
        encoding="utf-8",
    )
    errors = check_vector_literal_format(sql_dir)
    assert len(errors) == 1
    assert "missing leading '['" in errors[0]


def test_check_vector_literal_format_accepts_bracketed_string_literal(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "010_seed.sql").write_text(
        """\
INSERT INTO chunks (id, embedding) VALUES
    ('d1000000-0000-4000-8000-000000000001', '[0.01,0.02,0.03]'::vector);
""",
        encoding="utf-8",
    )
    assert check_vector_literal_format(sql_dir) == []


def test_check_vector_literal_format_rejects_concat_near_vector(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "010_seed.sql").write_text(
        """\
INSERT INTO chunks (id, embedding) VALUES
    ('d1000000-0000-4000-8000-000000000001',
     ('[' || '0.01,0.02' || ']')::vector);
""",
        encoding="utf-8",
    )
    errors = check_vector_literal_format(sql_dir)
    assert any("||" in e for e in errors)


def test_check_vector_literal_format_rejects_format_fn(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "010_seed.sql").write_text(
        """\
INSERT INTO chunks (id, embedding) VALUES
    ('d1000000-0000-4000-8000-000000000001',
     (SELECT format('%s', '0.01,0.02'))::vector);
""",
        encoding="utf-8",
    )
    errors = check_vector_literal_format(sql_dir)
    assert len(errors) == 1
    assert "format" in errors[0]


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


def test_check_ddl_column_drift_detects_renamed_column(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "001_create_departments.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS departments (
            id uuid PRIMARY KEY,
            name text NOT NULL,
            code text UNIQUE NOT NULL
        );
        """,
        encoding="utf-8",
    )
    # Live table predates the code/uuid redesign: integer PK, short_code instead of code.
    cur = _FakeCursor({("contacts_api", "departments"): ["id", "name", "short_code", "created_at"]})
    drift = check_ddl_column_drift(cur, app_schema="contacts_api", sql_dir=sql_dir)
    assert len(drift) == 1
    assert "code" in drift[0]
    assert "contacts_api.departments" in drift[0]
    assert "--reset-schema" in drift[0]


def test_check_ddl_column_drift_ignores_multiline_exclude_constraint(tmp_path: Path) -> None:
    """Regression: equipment-rental-app's EXCLUDE USING gist (...) WHERE (...) spans
    3 lines; only the first is prefix-skipped, so line-based parsing misread
    "daterange(reserved_from, reserved_to, '[]') WITH &&" and ") WHERE (status = ...)"
    as bogus columns and reported drift against a live table that actually matched."""
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "001_create_reservations.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS reservations (
            id SERIAL PRIMARY KEY,
            equipment_item_id INT NOT NULL,
            reserved_from DATE NOT NULL,
            reserved_to DATE NOT NULL,
            status reservation_status NOT NULL DEFAULT 'confirmed',
            CONSTRAINT chk_reservation_dates CHECK (reserved_to >= reserved_from),
            EXCLUDE USING gist (
                equipment_item_id WITH =,
                daterange(reserved_from, reserved_to, '[]') WITH &&
            ) WHERE (status = 'confirmed')
        );
        """,
        encoding="utf-8",
    )
    cur = _FakeCursor(
        {
            ("rental_app", "reservations"): [
                "id",
                "equipment_item_id",
                "reserved_from",
                "reserved_to",
                "status",
            ]
        }
    )
    drift = check_ddl_column_drift(cur, app_schema="rental_app", sql_dir=sql_dir)
    assert drift == []


def test_check_ddl_column_drift_clean_when_columns_match(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "001_create_departments.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS departments (
            id uuid PRIMARY KEY,
            name text NOT NULL,
            code text UNIQUE NOT NULL
        );
        """,
        encoding="utf-8",
    )
    cur = _FakeCursor({("contacts_api", "departments"): ["id", "name", "code", "created_at"]})
    assert check_ddl_column_drift(cur, app_schema="contacts_api", sql_dir=sql_dir) == []


def test_check_ddl_column_drift_skips_table_not_yet_created(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "001_create_departments.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS departments (
            id uuid PRIMARY KEY,
            code text UNIQUE NOT NULL
        );
        """,
        encoding="utf-8",
    )
    # No pre-existing table at all -> CREATE TABLE created it fresh, nothing to flag.
    cur = _FakeCursor({})
    assert check_ddl_column_drift(cur, app_schema="contacts_api", sql_dir=sql_dir) == []


def test_parse_create_table_columns_enrollments_ddl_real_fixture() -> None:
    """Real DDL from the failing app: a tight UNIQUE(...) must not become a column."""
    ddl = """
    CREATE TABLE IF NOT EXISTS enrollments (
        id SERIAL PRIMARY KEY,
        course_id INTEGER NOT NULL REFERENCES courses(id),
        student_user_id INTEGER NOT NULL REFERENCES users(id),
        status VARCHAR(20) NOT NULL DEFAULT 'enrolled' CHECK (status IN ('enrolled', 'completed', 'dropped')),
        grade_points DECIMAL(3,2) CHECK (grade_points BETWEEN 0.00 AND 4.00),
        enrolled_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE(course_id, student_user_id)
    );
    """
    specs = _parse_create_table_columns(ddl, source="enrollments.sql")
    names = {spec.name for spec in specs}
    assert names == {
        "id",
        "course_id",
        "student_user_id",
        "status",
        "grade_points",
        "enrolled_at",
        "updated_at",
    }
    # The column carrying an inline CHECK is the case most likely to regress if the
    # table-level-constraint skip is made too aggressive.
    assert "grade_points" in names
    # No bogus pseudo-column from the tight UNIQUE(...) constraint line.
    assert not any("(" in name for name in names)


def test_parse_create_table_columns_skips_all_table_level_constraint_forms() -> None:
    """Every standard table-level constraint form, tight and spaced against the paren."""
    ddl = """
    CREATE TABLE IF NOT EXISTS widgets (
        id SERIAL,
        a INTEGER NOT NULL,
        b INTEGER NOT NULL,
        parent_id INTEGER,
        status VARCHAR(20) NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY (parent_id) REFERENCES widgets(id),
        UNIQUE(a, b),
        UNIQUE (b, a),
        CHECK(status IN ('x')),
        CONSTRAINT widgets_status_valid CHECK (status IN ('x', 'y'))
    );
    """
    specs = _parse_create_table_columns(ddl, source="widgets.sql")
    names = {spec.name for spec in specs}
    assert names == {"id", "a", "b", "parent_id", "status"}
    assert not any("(" in name for name in names)


def test_parse_create_table_columns_keeps_column_with_inline_check() -> None:
    """A real column's own inline CHECK must not cause the column to be skipped."""
    ddl = """
    CREATE TABLE IF NOT EXISTS grades (
        id SERIAL PRIMARY KEY,
        grade_points DECIMAL(3,2) CHECK (grade_points BETWEEN 0.00 AND 4.00)
    );
    """
    specs = _parse_create_table_columns(ddl, source="grades.sql")
    names = {spec.name for spec in specs}
    assert names == {"id", "grade_points"}


def test_check_ddl_column_drift_ignores_table_level_unique_without_space(tmp_path: Path) -> None:
    """Regression: compliance-management incident (run abfee325-...).

    A table-level ``UNIQUE(document_id, version_number)`` constraint with no
    space before the parenthesis used to slip past ``_SKIP_COLUMN_PREFIXES``
    (whose exact-token check only matched a bare "UNIQUE"), getting misparsed
    as a literal column named "UNIQUE(document_id," — a false-positive drift
    that failed the whole database-agent step for a schema with no real drift.
    """
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "001_create_document_versions.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS document_versions (
            id uuid PRIMARY KEY,
            document_id uuid NOT NULL,
            version_number int NOT NULL,
            UNIQUE(document_id, version_number)
        );
        """,
        encoding="utf-8",
    )
    cur = _FakeCursor(
        {("compliance_management", "document_versions"): ["id", "document_id", "version_number"]}
    )
    assert check_ddl_column_drift(cur, app_schema="compliance_management", sql_dir=sql_dir) == []


def test_check_seed_conflict_on_ruled_tables_detects_incident(tmp_path: Path) -> None:
    """Regression: insurance-claims incident (run 49b51e3a-...).

    009_add_history_no_update_delete_rule.sql adds UPDATE/DELETE rules to
    claim_history for an append-only pattern; 010_seed.sql then seeds that
    same table with ON CONFLICT DO NOTHING. PostgreSQL rejects ON CONFLICT on
    any table with any rule, regardless of the rule's own event type — this
    fails even on a freshly-reset schema, so it's a real generation bug, not
    a drift/staleness issue.
    """
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "007_create_claim_history.sql").write_text(
        """
        CREATE TABLE IF NOT EXISTS claim_history (
            id uuid PRIMARY KEY,
            claim_id uuid NOT NULL,
            event_type text NOT NULL
        );
        """,
        encoding="utf-8",
    )
    (sql_dir / "009_add_history_no_update_delete_rule.sql").write_text(
        """
        CREATE RULE prevent_update_claim_history AS
            ON UPDATE TO claim_history
            DO INSTEAD NOTHING;

        CREATE RULE prevent_delete_claim_history AS
            ON DELETE TO claim_history
            DO INSTEAD NOTHING;
        """,
        encoding="utf-8",
    )
    (sql_dir / "010_seed.sql").write_text(
        """
        INSERT INTO claim_history (id, claim_id, event_type) VALUES
            ('00000001-aaaa-0000-0000-000000000001', 'c1', 'status_change')
        ON CONFLICT DO NOTHING;
        """,
        encoding="utf-8",
    )
    errors = check_seed_conflict_on_ruled_tables(sql_dir)
    assert len(errors) == 1
    assert "claim_history" in errors[0]
    assert "ON CONFLICT" in errors[0]
    assert "010_seed.sql" in errors[0]


def test_check_seed_conflict_on_ruled_tables_clean_when_no_rules(tmp_path: Path) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "001_create_users.sql").write_text(
        "CREATE TABLE IF NOT EXISTS users (id uuid PRIMARY KEY, name text NOT NULL);",
        encoding="utf-8",
    )
    (sql_dir / "002_seed.sql").write_text(
        "INSERT INTO users (id, name) VALUES ('00000001-0000-0000-0000-000000000001', 'a')"
        " ON CONFLICT DO NOTHING;",
        encoding="utf-8",
    )
    assert check_seed_conflict_on_ruled_tables(sql_dir) == []


def test_check_seed_conflict_on_ruled_tables_clean_when_seed_has_no_on_conflict(tmp_path: Path) -> None:
    """A ruled table is fine to seed as long as the INSERT doesn't use ON CONFLICT."""
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "007_create_claim_history.sql").write_text(
        "CREATE TABLE IF NOT EXISTS claim_history (id uuid PRIMARY KEY, event_type text NOT NULL);",
        encoding="utf-8",
    )
    (sql_dir / "009_rule.sql").write_text(
        "CREATE RULE prevent_update_claim_history AS ON UPDATE TO claim_history DO INSTEAD NOTHING;",
        encoding="utf-8",
    )
    (sql_dir / "010_seed.sql").write_text(
        "INSERT INTO claim_history (id, event_type) VALUES "
        "('00000001-0000-0000-0000-000000000001', 'status_change');",
        encoding="utf-8",
    )
    assert check_seed_conflict_on_ruled_tables(sql_dir) == []


def test_split_sql_statements_still_importable_after_move() -> None:
    """split_sql_statements moved from apply_sql_to_rds.py into this shared module
    (apply_sql_to_rds.py now imports it) so validate_sql_artifacts.py can reuse it
    without a reverse dependency on scripts/. Guard the public contract directly."""
    stmts = split_sql_statements("INSERT INTO a VALUES ('x;y'); INSERT INTO b VALUES (1);")
    assert len(stmts) == 2
    assert "x;y" in stmts[0]
