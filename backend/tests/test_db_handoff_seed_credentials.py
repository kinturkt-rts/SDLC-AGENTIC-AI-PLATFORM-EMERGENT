"""Host copies ### seedCredentials from the agent reply into HANDOFF.md."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.db_handoff import build_handoff_markdown, extract_agent_section  # noqa: E402


def test_extract_seed_credentials_section() -> None:
    reply = """\
### schema_summary
- 2 tables

### seedCredentials
| username | role  | plaintext_password |
|----------|-------|--------------------|
| alice    | admin | YourPassword123!   |

### handoff_for_developer
- use SQLAlchemy
"""
    body = extract_agent_section(reply, "seedCredentials")
    assert "alice" in body
    assert "YourPassword123!" in body


def test_build_handoff_copies_seed_credentials_from_reply(tmp_path: Path) -> None:
    sql_dir = tmp_path / "fixture-app" / "db" / "sql"
    sql_dir.mkdir(parents=True)
    (sql_dir / "001_users.sql").write_text(
        "CREATE TABLE users (id uuid PRIMARY KEY);\n",
        encoding="utf-8",
    )
    reply = """\
### schema_summary
- users

### seedCredentials
| username | role  | plaintext_password |
|----------|-------|--------------------|
| alice    | admin | DemoPass123!       |
"""
    md = build_handoff_markdown(
        target_app="fixture-app",
        ctx={
            "preferredSqlPath": "fixture-app/db/sql",
            "postgresAppSchema": "fixture_app",
        },
        agent_result=reply,
        repo_root=tmp_path,
    )
    assert "### seedCredentials" in md
    assert "alice" in md
    assert "DemoPass123!" in md


def test_build_handoff_omits_seed_credentials_when_absent(tmp_path: Path) -> None:
    sql_dir = tmp_path / "fixture-app" / "db" / "sql"
    sql_dir.mkdir(parents=True)
    md = build_handoff_markdown(
        target_app="fixture-app",
        ctx={"preferredSqlPath": "fixture-app/db/sql"},
        agent_result="### schema_summary\n- ok\n",
        repo_root=tmp_path,
    )
    assert "### seedCredentials" not in md
