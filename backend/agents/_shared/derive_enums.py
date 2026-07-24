"""Derive Pydantic Literal types from applied Postgres enums.

Runs after the DB schema is applied and after the developer agent writes files,
before openapi.json is generated. Reads enum values from the applied database
for an app and rewrites bare `str` fields in that app's response schemas to
Literal[...] with the real values, so the enums reach the OpenAPI spec.

Safe: idempotent, never raises, skips ambiguous column names rather than guessing.
"""
from __future__ import annotations

import re
from pathlib import Path

from _shared.rds_env import connection_url, load_target_app_env, schema_for_app

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_enum_columns(app_schema: str, url: str) -> dict[str, list[str]]:
    """Return {column_name: [values]} for enum-typed columns in the schema.

    A column name that appears with DIFFERENT enum value sets on different
    tables is treated as ambiguous and dropped (skipped, not guessed).
    """
    import psycopg

    # t.typname = c.udt_name matches by NAME ONLY — Postgres allows the same enum
    # type name (e.g. "user_role") to exist independently in every app's schema on
    # this shared RDS instance, so without the pg_namespace join below, this pulls
    # in enum labels from every OTHER app's same-named type too (real cross-schema
    # contamination confirmed live: clinic_scheduler.user_role, it_asset_lifecycle.user_role,
    # audit_finding_tracker.user_role, employee_leave_manager.user_role all merged into
    # one column's value set). n.nspname = c.table_schema pins the type to the SAME
    # schema as the column being inspected.
    q = """
        SELECT c.column_name, t.typname, e.enumlabel, e.enumsortorder
        FROM information_schema.columns c
        JOIN pg_type t ON t.typname = c.udt_name
        JOIN pg_namespace n ON n.oid = t.typnamespace AND n.nspname = c.table_schema
        JOIN pg_enum e ON e.enumtypid = t.oid
        WHERE c.table_schema = %s
        ORDER BY c.column_name, e.enumsortorder
    """
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(q, (app_schema,))
        rows = cur.fetchall()

    grouped: dict[tuple[str, str], list[str]] = {}
    for col, typ, label, _order in rows:
        grouped.setdefault((col, typ), []).append(label)

    seen: dict[str, set[tuple[str, ...]]] = {}
    values_by_col: dict[str, list[str]] = {}
    for (col, _typ), vals in grouped.items():
        seen.setdefault(col, set()).add(tuple(vals))
        values_by_col[col] = vals

    result: dict[str, list[str]] = {}
    for col, valuesets in seen.items():
        if len(valuesets) == 1:
            result[col] = values_by_col[col]
        else:
            print(f"[derive-enums]   SKIP ambiguous column '{col}'")
    return result


def _literal_for(values: list[str]) -> str:
    return "Literal[" + ", ".join(f'"{v}"' for v in values) + "]"


def _rewrite_file(path: Path, enum_cols: dict[str, list[str]]) -> list[str]:
    text = path.read_text(encoding="utf-8")
    original = text
    changes: list[str] = []

    for col, values in enum_cols.items():
        literal = _literal_for(values)
        pattern = re.compile(
            rf"^(?P<indent>[ \t]+){re.escape(col)}:[ \t]+str[ \t]*$",
            re.MULTILINE,
        )
        new_text, n = pattern.subn(
            lambda m: f"{m.group('indent')}{col}: {literal}", text
        )
        if n:
            text = new_text
            changes.append(f"{path.name}: {col} -> {literal} ({n})")

    if text != original and "Literal[" in text:
        if re.search(r"^from typing import .+$", text, re.MULTILINE):
            text = re.sub(
                r"^(from typing import )(.+)$",
                lambda m: m.group(1)
                + ("Literal, " + m.group(2) if "Literal" not in m.group(2) else m.group(2)),
                text,
                count=1,
                flags=re.MULTILINE,
            )
        elif "from __future__" in text:
            text = text.replace(
                "from __future__ import annotations\n",
                "from __future__ import annotations\n\nfrom typing import Literal\n",
                1,
            )
        else:
            text = "from typing import Literal\n" + text

    if text != original:
        path.write_text(text, encoding="utf-8")
    return changes


def derive_enums_for_app(target_app: str) -> str:
    """Main entry. Returns a summary string. Never raises."""
    try:
        load_target_app_env(target_app)
        app_schema = schema_for_app(target_app)
        url = connection_url().replace("postgresql+psycopg://", "postgresql://")

        enum_cols = _read_enum_columns(app_schema, url)
        if not enum_cols:
            return f"[derive-enums] {target_app}: no enum columns in '{app_schema}', nothing to do."

        schemas_dir = _REPO_ROOT / "target-apps" / target_app / "schemas"
        if not schemas_dir.is_dir():
            return f"[derive-enums] {target_app}: no schemas/ dir, skipped."

        all_changes: list[str] = []
        for py in sorted(schemas_dir.glob("*.py")):
            if py.name == "__init__.py":
                continue
            all_changes.extend(_rewrite_file(py, enum_cols))

        if not all_changes:
            return f"[derive-enums] {target_app}: enums exist but no bare-str fields to fix (already correct)."
        return f"[derive-enums] {target_app}: fixed:\n  " + "\n  ".join(all_changes)
    except Exception as exc:  # never break the pipeline
        return f"[derive-enums] {target_app}: ERROR (non-fatal): {exc!r}"