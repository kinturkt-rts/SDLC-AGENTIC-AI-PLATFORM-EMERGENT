"""Validate sql/ artifacts and reconcile nullable column drift on RDS.

Catches the common pipeline failure: seed INSERT uses NULL for an optional column
while an older RDS table still has NOT NULL from a prior CREATE TABLE IF NOT EXISTS run.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"((?:[a-zA-Z_][\w]*\.)?[a-zA-Z_][\w]*)\s*\(",
    re.IGNORECASE,
)
_INSERT_INTO_RE = re.compile(
    r"INSERT\s+INTO\s+((?:[a-zA-Z_][\w]*\.)?[a-zA-Z_][\w]*)\s*\(",
    re.IGNORECASE,
)
_SKIP_COLUMN_PREFIXES = (
    "CONSTRAINT",
    "PRIMARY",
    "UNIQUE",
    "CHECK",
    "FOREIGN",
    "EXCLUDE",
)


@dataclass(frozen=True)
class ColumnSpec:
    schema: str | None
    table: str
    name: str
    not_null: bool


@dataclass(frozen=True)
class InsertRow:
    source_file: str
    schema: str | None
    table: str
    columns: tuple[str, ...]
    values: tuple[str | None, ...]


def _strip_sql_comments(sql: str) -> str:
    lines: list[str] = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _split_qualified_name(name: str) -> tuple[str | None, str]:
    cleaned = name.strip().strip('"')
    if "." in cleaned:
        schema, table = cleaned.rsplit(".", 1)
        return schema, table
    return None, cleaned


def _find_matching_paren(text: str, open_index: int) -> int:
    depth = 0
    in_single = False
    i = open_index
    while i < len(text):
        ch = text[i]
        if ch == "'" and not in_single:
            in_single = True
        elif ch == "'" and in_single:
            if i + 1 < len(text) and text[i + 1] == "'":
                i += 1
            else:
                in_single = False
        elif not in_single:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise ValueError("unbalanced parentheses in CREATE TABLE")


def _column_not_null(line: str) -> bool:
    upper = line.upper()
    if " NOT NULL" in upper:
        return True
    if re.search(r"\bPRIMARY\s+KEY\b", upper):
        return True
    return False


def _parse_create_table_columns(sql: str, *, source: str) -> list[ColumnSpec]:
    specs: list[ColumnSpec] = []
    cleaned = _strip_sql_comments(sql)
    for match in _CREATE_TABLE_RE.finditer(cleaned):
        table_ref = match.group(1)
        schema, table = _split_qualified_name(table_ref)
        open_paren = match.end() - 1
        close_paren = _find_matching_paren(cleaned, open_paren)
        body = cleaned[open_paren + 1 : close_paren]
        for raw_line in body.splitlines():
            line = raw_line.strip().rstrip(",")
            if not line:
                continue
            first = line.split(None, 1)[0].upper()
            if first in _SKIP_COLUMN_PREFIXES:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            col_name = parts[0].strip('"')
            specs.append(
                ColumnSpec(
                    schema=schema,
                    table=table,
                    name=col_name,
                    not_null=_column_not_null(line),
                )
            )
    return specs


def _split_csv_outside_quotes(text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    in_single = False
    depth = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "'" and not in_single:
            in_single = True
            buf.append(ch)
        elif ch == "'" and in_single:
            if i + 1 < len(text) and text[i + 1] == "'":
                buf.append("''")
                i += 1
            else:
                in_single = False
            buf.append(ch)
        elif not in_single:
            if ch == "(":
                depth += 1
                buf.append(ch)
            elif ch == ")":
                depth -= 1
                buf.append(ch)
            elif ch == "," and depth == 0:
                parts.append("".join(buf).strip())
                buf = []
            else:
                buf.append(ch)
        else:
            buf.append(ch)
        i += 1
    if buf:
        parts.append("".join(buf).strip())
    return parts


def _normalize_sql_value(token: str) -> str | None:
    stripped = token.strip()
    if not stripped or stripped.upper() == "NULL":
        return None
    return stripped


def _split_value_rows(values_sql: str) -> list[str]:
    rows: list[str] = []
    depth = 0
    start = -1
    in_single = False
    i = 0
    while i < len(values_sql):
        ch = values_sql[i]
        if ch == "'" and not in_single:
            in_single = True
        elif ch == "'" and in_single:
            if i + 1 < len(values_sql) and values_sql[i + 1] == "'":
                i += 1
            else:
                in_single = False
        elif not in_single:
            if ch == "(":
                if depth == 0:
                    start = i + 1
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and start >= 0:
                    rows.append(values_sql[start:i].strip())
                    start = -1
        i += 1
    return rows


def _parse_insert_statements(sql: str, *, source: str) -> list[InsertRow]:
    rows: list[InsertRow] = []
    cleaned = _strip_sql_comments(sql)
    pos = 0
    while True:
        match = _INSERT_INTO_RE.search(cleaned, pos)
        if not match:
            break
        table_ref = match.group(1)
        schema, table = _split_qualified_name(table_ref)
        col_open = match.end()
        col_close = _find_matching_paren(cleaned, col_open - 1)
        col_list = cleaned[col_open:col_close]
        columns = tuple(
            c.strip().strip('"')
            for c in _split_csv_outside_quotes(col_list)
            if c.strip()
        )
        rest = cleaned[col_close + 1 :]
        values_match = re.search(r"\bVALUES\b", rest, re.IGNORECASE)
        if not values_match:
            pos = col_close + 1
            continue
        values_part = rest[values_match.end() :]
        conflict_match = re.search(r"\bON\s+CONFLICT\b", values_part, re.IGNORECASE)
        if conflict_match:
            values_part = values_part[: conflict_match.start()]
        values_part = values_part.strip().rstrip(";")
        for row_sql in _split_value_rows(values_part):
            values = tuple(_normalize_sql_value(v) for v in _split_csv_outside_quotes(row_sql))
            if len(values) != len(columns):
                continue
            rows.append(
                InsertRow(
                    source_file=source,
                    schema=schema,
                    table=table,
                    columns=columns,
                    values=values,
                )
            )
        pos = col_close + 1
    return rows


def _schema_key(schema: str | None, table: str) -> tuple[str | None, str]:
    return schema, table


def parse_schema_nullability(sql_dir: Path) -> dict[tuple[str | None, str, str], bool]:
    """Map (schema, table, column) -> not_null from all non-seed sql files."""
    result: dict[tuple[str | None, str, str], bool] = {}
    for path in sorted(sql_dir.glob("*.sql")):
        if "seed" in path.name.lower():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for spec in _parse_create_table_columns(text, source=path.name):
            key = (spec.schema, spec.table, spec.name)
            result[key] = spec.not_null
    return result


def parse_seed_inserts(sql_dir: Path) -> list[InsertRow]:
    inserts: list[InsertRow] = []
    for path in sorted(sql_dir.glob("*.sql")):
        if "seed" not in path.name.lower():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        inserts.extend(_parse_insert_statements(text, source=path.name))
    return inserts


def check_seed_schema_nullability(sql_dir: Path) -> list[str]:
    """Fail when seed INSERT supplies NULL for a column marked NOT NULL in DDL."""
    if not sql_dir.is_dir():
        return []

    nullability = parse_schema_nullability(sql_dir)
    if not nullability:
        return []

    errors: list[str] = []
    for insert in parse_seed_inserts(sql_dir):
        for col, val in zip(insert.columns, insert.values, strict=True):
            if val is not None:
                continue
            key = (insert.schema, insert.table, col)
            alt_key = (None, insert.table, col)
            not_null = nullability.get(key)
            if not_null is None:
                not_null = nullability.get(alt_key)
            if not_null:
                qual = f"{insert.schema}.{insert.table}" if insert.schema else insert.table
                errors.append(
                    f"{insert.source_file}: INSERT INTO {qual} sets NULL for column {col!r} "
                    f"but DDL marks it NOT NULL — make the column nullable in schema SQL "
                    f"(optional fields: omit NOT NULL) or provide a non-NULL seed value"
                )
    return errors


_UUID_LITERAL_RE = re.compile(
    r"'([0-9a-zA-Z]{8}-[0-9a-zA-Z]{4}-[0-9a-zA-Z]{4}-[0-9a-zA-Z]{4}-[0-9a-zA-Z]{12})'"
)
_VALID_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


_BARE_SEARCH_PATH_RE = re.compile(
    r"SET\s+search_path\s*=\s*public\s*;",
    re.IGNORECASE,
)


def check_bare_search_path(sql_dir: Path) -> list[str]:
    """Detect SET search_path = public (bare, no app schema) which breaks cross-file type lookups.

    apply_sql_to_rds.py sets search_path = <app_schema>, public at the connection level.
    A bare 'SET search_path = public' in any migration file overrides that and hides enums/types
    created in the app schema by earlier migrations (causes 'type does not exist' errors).
    """
    errors: list[str] = []
    for path in sorted(sql_dir.glob("*.sql")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if _BARE_SEARCH_PATH_RE.search(text):
            errors.append(
                f"{path.name}: 'SET search_path = public' without app schema — "
                f"this hides enums/types from earlier migrations and causes 'type does not exist' errors. "
                f"Remove the SET statement (apply_sql_to_rds.py already sets the correct search_path) "
                f"or use 'SET search_path = <app_schema>, public'."
            )
    return errors


def check_uuid_literals(sql_dir: Path) -> list[str]:
    """Reject UUID-shaped literals that contain non-hex characters (g-z)."""
    errors: list[str] = []
    for path in sorted(sql_dir.glob("*.sql")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in _UUID_LITERAL_RE.finditer(text):
            candidate = match.group(1)
            if not _VALID_UUID_RE.match(candidate):
                bad_chars = sorted(set(c for c in candidate.replace("-", "") if c.lower() not in "0123456789abcdef"))
                errors.append(
                    f"{path.name}: invalid UUID literal '{candidate}' — "
                    f"non-hex character(s): {', '.join(bad_chars)}. "
                    f"UUIDs may only contain 0-9 and a-f."
                )
    return errors


def validate_sql_dir(sql_dir: Path) -> list[str]:
    """Run all blocking sql/ artifact checks."""
    errors = check_seed_schema_nullability(sql_dir)
    errors.extend(check_uuid_literals(sql_dir))
    errors.extend(check_bare_search_path(sql_dir))
    return errors


def _nullability_reconcile_enabled() -> bool:
    import os

    flag = os.getenv("RDS_SKIP_NULLABILITY_RECONCILE", "").strip().lower()
    return flag not in ("1", "true", "yes")


def reconcile_nullability_from_ddl(
    cur: object,
    *,
    app_schema: str,
    sql_dir: Path,
    verbose: bool = False,
) -> list[str]:
    """ALTER COLUMN DROP NOT NULL when DDL allows NULL but RDS still has NOT NULL.

    Fixes stale tables from CREATE TABLE IF NOT EXISTS when an earlier run used
    stricter nullability. Safe for dev RDS re-runs; disable with RDS_SKIP_NULLABILITY_RECONCILE=1.
    """
    if not _nullability_reconcile_enabled():
        return []

    from psycopg import sql as psql

    nullability = parse_schema_nullability(sql_dir)
    alters: list[str] = []
    tables: set[tuple[str | None, str]] = set()
    for schema, table, _col in nullability:
        tables.add((schema, table))

    for schema, table in sorted(tables):
        effective_schema = schema or app_schema
        cur.execute(
            """
            SELECT column_name, is_nullable
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            """,
            (effective_schema, table),
        )
        db_cols = {row[0]: row[1] for row in cur.fetchall()}
        for (spec_schema, spec_table, col_name), not_null in nullability.items():
            if spec_table != table:
                continue
            if spec_schema not in (None, effective_schema):
                continue
            if not_null:
                continue
            if col_name not in db_cols:
                continue
            if db_cols[col_name] == "YES":
                continue
            stmt = psql.SQL("ALTER TABLE {}.{} ALTER COLUMN {} DROP NOT NULL").format(
                psql.Identifier(effective_schema),
                psql.Identifier(table),
                psql.Identifier(col_name),
            )
            cur.execute(stmt)
            msg = f"{effective_schema}.{table}.{col_name} DROP NOT NULL (DDL allows NULL; RDS was NOT NULL)"
            alters.append(msg)
            if verbose:
                print(f"  Reconciled: {msg}", file=sys.stderr)
    return alters
