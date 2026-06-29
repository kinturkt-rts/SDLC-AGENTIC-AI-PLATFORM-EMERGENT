"""Write target-apps/<app>/db/HANDOFF.md after database-agent runs."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLATFORM_STACK = (
    "Python 3.12+",
    "FastAPI + Pydantic v2",
    "SQLAlchemy 2.x (recommended for RDS models)",
    "uvicorn",
)
_TEMPLATE_REQUIREMENTS = "target-apps/_template/requirements.txt"


def extract_agent_section(agent_result: str, section: str) -> str:
    """Pull a ### section body from the database-agent markdown reply."""
    if not agent_result.strip():
        return ""
    pattern = rf"###\s*{re.escape(section)}\s*\r?\n(.*?)(?=\r?\n###\s|\Z)"
    match = re.search(pattern, agent_result, re.DOTALL | re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip()


def sorted_sql_artifacts(sql_dir: Path) -> list[str]:
    if not sql_dir.is_dir():
        return []
    return [p.name for p in sorted(sql_dir.glob("*.sql"), key=lambda x: x.name)]


def _infer_orm_notes_from_sql(sql_dir: Path, schema: str) -> list[str]:
    """Scan migrations for ENUM/uuid patterns developer-agent must mirror in ORM."""
    if not sql_dir.is_dir():
        return []
    combined = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in sorted(sql_dir.glob("*.sql"))
    )
    notes: list[str] = []
    enums = re.findall(
        r"CREATE\s+TYPE\s+(?:\w+\.)?(\w+)\s+AS\s+ENUM\s*\(([^)]+)\)",
        combined,
        flags=re.IGNORECASE,
    )
    for name, _values in enums:
        notes.append(
            f"- **ENUM `{name}`** → `sqlalchemy.Enum(..., name='{name}', "
            f"schema='{schema}', create_type=False, native_enum=True)` "
            f"+ `.with_variant(String, 'sqlite')` (see `_template/app/models/pg_types.py`)."
        )
    if re.search(r"\buuid\b", combined, re.IGNORECASE):
        notes.append(
            "- **uuid columns** → `PG_UUID(as_uuid=False).with_variant(String(36), 'sqlite')`; "
            "Pydantic response schemas: coerce `UUID` → `str` in `@field_validator`."
        )
    notes.append(
        "- **Driver/DSN** → `psycopg[binary]` in requirements; "
        "`.env.example`: `postgresql+psycopg://...?sslmode=require`; "
        f"`POSTGRES_SCHEMA={schema}` (set search_path in `database.py`, not copied from other apps)."
    )
    return notes


def build_handoff_markdown(
    *,
    target_app: str,
    ctx: dict[str, Any],
    agent_result: str = "",
    rds_applied: bool = False,
    repo_root: Path | None = None,
) -> str:
    """Assemble HANDOFF.md for developer-agent."""
    root = repo_root or _REPO_ROOT
    slug = target_app.strip()
    schema = (ctx.get("postgresAppSchema") or slug.replace("-", "_")).strip()
    sql_rel = ctx.get("preferredSqlPath") or f"target-apps/{slug}/db/sql"
    sql_dir = (root / sql_rel).resolve()
    artifacts = sorted_sql_artifacts(sql_dir)

    params = ctx.get("postgresMcpParams") or {}
    endpoint = params.get("db_endpoint") or "(set POSTGRES_MCP_DB_ENDPOINT)"
    database = params.get("database") or "(set POSTGRES_MCP_DATABASE)"

    schema_summary = extract_agent_section(agent_result, "schema_summary")
    handoff_notes = extract_agent_section(agent_result, "handoff_for_developer")

    seed_min = ctx.get("seedMinRows", "")
    seed_max = ctx.get("seedMaxRows", "")

    lines = [
        f"# Database handoff — {slug}",
        "",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by database-agent._",
        "",
        "## For developer-agent",
        "",
        "Read this file with `dev_read_file` before implementing models and repositories.",
        "Primary API and business rules remain in `designDocPath` (§4–§5).",
        "",
        "## Application stack (platform default)",
        "",
        "Downstream services are **Python**, not chosen per app in `requirements.txt` from database-agent.",
        "Developer-agent scaffolds from `target-apps/_template/` and uses:",
        "",
    ]
    for item in _PLATFORM_STACK:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            f"Base dependencies: `{_TEMPLATE_REQUIREMENTS}` (FastAPI, uvicorn, pydantic).",
            "Add `sqlalchemy`, `psycopg[binary]`, and `alembic` in the service `requirements.txt` when wiring RDS.",
            "",
            "## RDS target",
            "",
            f"| Item | Value |",
            f"|------|--------|",
            f"| Postgres schema | `{schema}` |",
            f"| Database | `{database}` |",
            f"| Endpoint | `{endpoint}` |",
            f"| SQL artifacts | `{sql_rel}/` |",
            f"| RDS apply (last run) | {'yes — apply_sql_to_rds.py' if rds_applied else 'not this session'} |",
        ]
    )
    if seed_min != "" and seed_max != "":
        lines.append(f"| Dev seed rows/table | {seed_min}–{seed_max} (see `*_seed.sql`) |")

    lines.extend(["", "## SQL files (apply order)", ""])
    if artifacts:
        for idx, name in enumerate(artifacts, start=1):
            lines.append(f"{idx}. `{sql_rel}/{name}`")
    else:
        lines.append("(no `.sql` files found yet)")

    lines.append("")
    lines.append("**Connection:** load credentials from env/Key Vault (NFR-5). "
                 f"Use schema `{schema}` (`search_path` or qualified table names). "
                 "Do not rely on unqualified `public` for app tables.")

    if schema_summary:
        lines.extend(["", "## Schema summary (database-agent)", "", schema_summary])

    if handoff_notes:
        lines.extend(["", "## Implementation notes (database-agent)", "", handoff_notes])

    orm_notes = _infer_orm_notes_from_sql(sql_dir, schema)
    if orm_notes:
        lines.extend(["", "## ORM parity (required for live RDS)", "", *orm_notes])

    lines.extend(
        [
            "",
            "## Developer-agent checklist",
            "",
            f"1. `dev_read_file` → `{ctx.get('designDocPath', f'docs/design/{slug}.md')}`",
            f"2. `dev_read_file` → `{sql_rel}/` migrations + seed",
            "3. Scaffold `target-apps/<app>/` from `_template` if empty; extend `requirements.txt` for DB libs",
            "4. SQLAlchemy models aligned with DDL (ENUM + uuid rules above); Pydantic schemas for §4 API",
            f"5. README: Windows+bash setup, `.env` copy, uvicorn, Swagger auth, seed UUIDs, RDS smoke test",
            f"6. `pytest tests/ -q` passes; engineer smoke-tests one DB list route against RDS after `.env` is set",
            "",
        ]
    )
    return "\n".join(lines)


def write_db_handoff(
    target_app: str,
    ctx: dict[str, Any],
    *,
    agent_result: str = "",
    rds_applied: bool = False,
    repo_root: Path | None = None,
) -> str:
    """Write HANDOFF.md under db/; return repo-relative path."""
    from _shared.artifact_store import resolve_run_id, write_repo_artifact

    root = repo_root or _REPO_ROOT
    slug = target_app.strip()
    db_rel = ctx.get("dbOutputDir") or f"target-apps/{slug}/db"
    db_dir = (root / db_rel).resolve()
    db_dir.mkdir(parents=True, exist_ok=True)
    content = build_handoff_markdown(
        target_app=slug,
        ctx=ctx,
        agent_result=agent_result,
        rds_applied=rds_applied,
        repo_root=root,
    )
    handoff_rel = f"{db_rel.rstrip('/')}/HANDOFF.md"
    run_id = resolve_run_id(ctx)
    if run_id:
        write_repo_artifact(handoff_rel, content, context=ctx)
    handoff_path = db_dir / "HANDOFF.md"
    handoff_path.write_text(content, encoding="utf-8", newline="\n")
    try:
        return handoff_path.relative_to(root).as_posix()
    except ValueError:
        return handoff_rel
