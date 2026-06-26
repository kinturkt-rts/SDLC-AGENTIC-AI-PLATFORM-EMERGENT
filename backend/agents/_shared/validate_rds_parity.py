"""Static checks for RDS vs SQLite-test false greens (timestamps, seed materialize, uvicorn)."""

from __future__ import annotations

import re
from pathlib import Path

from _shared.seed_credentials import collect_credentials, seed_sql_has_placeholders

_TIMESTAMP_COL_RE = re.compile(
    r"\b(created_at|updated_at|published_at|archived_at|pinned_at|timestamp)\b",
    re.IGNORECASE,
)
_SCHEMA_TS_STR_RE = re.compile(
    r"^\s*(created_at|updated_at|published_at|archived_at|pinned_at|timestamp)\s*:\s*str\b",
    re.MULTILINE | re.IGNORECASE,
)
_MODEL_TS_TEXT_RE = re.compile(
    r"\b(created_at|updated_at|published_at|archived_at|pinned_at|timestamp)\b"
    r"[\s\S]{0,200}?mapped_column\s*\(\s*Text\b",
    re.IGNORECASE,
)
_DDL_TIMESTAMPTZ_RE = re.compile(r"\bTIMESTAMPTZ\b", re.IGNORECASE)


def check_seed_materialize_parseable(app_dir: Path) -> list[str]:
    """Fail when placeholders exist but materialize cannot find users to update."""
    if not seed_sql_has_placeholders(app_dir):
        return []
    creds = collect_credentials(app_dir)
    if creds:
        return []
    return [
        f"{app_dir.name}: seed SQL has __BCRYPT_PLACEHOLDER__ but collect_credentials() "
        "returned no users — add ### seedCredentials to db/HANDOFF.md and/or ensure "
        "users INSERT lists email/username + hash columns parseably (see seed_credentials.py)"
    ]


def _sql_uses_timestamptz(app_dir: Path) -> bool:
    sql_dir = app_dir / "db" / "sql"
    if not sql_dir.is_dir():
        return False
    for path in sql_dir.glob("*.sql"):
        if _DDL_TIMESTAMPTZ_RE.search(path.read_text(encoding="utf-8", errors="replace")):
            return True
    return False


def check_timestamp_orm_schema_parity(app_dir: Path) -> list[str]:
    """Catch Text ORM + str schemas when DDL uses TIMESTAMPTZ (RDS returns datetime → 500)."""
    if not _sql_uses_timestamptz(app_dir):
        return []

    errors: list[str] = []
    models_dir = app_dir / "app" / "models"
    if models_dir.is_dir():
        for path in models_dir.glob("*.py"):
            if path.name.startswith("_"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if _MODEL_TS_TEXT_RE.search(text):
                rel = path.relative_to(app_dir).as_posix()
                errors.append(
                    f"{rel}: timestamp column mapped as Text — use TimestampTZ from "
                    "app.models.pg_types (DateTime(timezone=True)) to match TIMESTAMPTZ DDL"
                )

    schemas_dir = app_dir / "schemas"
    if schemas_dir.is_dir():
        for path in schemas_dir.glob("*.py"):
            if path.name in ("__init__.py", "common.py"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if not _SCHEMA_TS_STR_RE.search(text):
                continue
            has_coercion = (
                "coerce_iso_datetime" in text
                or "coerce_timestamps" in text
                or re.search(
                    r"field_validator\(\s*[\"'].*_at",
                    text,
                )
            )
            if not has_coercion:
                rel = path.relative_to(app_dir).as_posix()
                errors.append(
                    f"{rel}: response schema uses *_at: str without datetime coercion — "
                    "import coerce_iso_datetime from schemas.common and add field_validator "
                    "(RDS TIMESTAMPTZ returns datetime; SQLite tests use strings → false green)"
                )

    common = schemas_dir / "common.py"
    if errors and schemas_dir.is_dir() and not common.is_file():
        errors.append(
            "schemas/common.py missing — scaffold coerce_iso_datetime() from "
            "target-apps/_template/schemas/common.py"
        )
    return errors


def check_readme_uvicorn_reload(app_dir: Path) -> list[str]:
    """Warn when README tells users to run bare --reload (watches .venv → reload storms)."""
    readme = app_dir / "README.md"
    if not readme.is_file():
        return []
    text = readme.read_text(encoding="utf-8", errors="replace")
    if "uvicorn" not in text.lower():
        return []
    if "--reload-dir" in text:
        return []
    if re.search(r"uvicorn\s+app\.main:app\s+--reload\b", text):
        return [
            f"{app_dir.name}/README.md: uvicorn --reload without --reload-dir app "
            "(and schemas if present) — pytest edits .venv and causes API timeouts"
        ]
    return []


def validate_rds_parity(app_dir: Path) -> list[str]:
    """Run all RDS parity checks; return blocking error messages."""
    errors: list[str] = []
    errors.extend(check_seed_materialize_parseable(app_dir))
    errors.extend(check_timestamp_orm_schema_parity(app_dir))
    sql_dir = app_dir / "db" / "sql"
    if sql_dir.is_dir():
        from _shared.validate_sql_artifacts import validate_sql_dir

        errors.extend(validate_sql_dir(sql_dir))
    return errors


def validate_rds_parity_warnings(app_dir: Path) -> list[str]:
    """Non-blocking warnings (README / ops)."""
    return check_readme_uvicorn_reload(app_dir)
