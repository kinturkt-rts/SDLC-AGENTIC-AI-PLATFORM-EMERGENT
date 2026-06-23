"""Tests for database HANDOFF.md generation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.db_handoff import build_handoff_markdown, extract_agent_section, write_db_handoff


def test_extract_agent_section() -> None:
    text = "### schema_summary\n- 6 tables\n\n### handoff_for_developer\n- Use SQLAlchemy\n"
    assert "6 tables" in extract_agent_section(text, "schema_summary")
    assert "SQLAlchemy" in extract_agent_section(text, "handoff_for_developer")


def test_build_handoff_includes_stack_and_schema() -> None:
    md = build_handoff_markdown(
        target_app="meeting-assistant",
        ctx={
            "postgresAppSchema": "meeting_assistant",
            "preferredSqlPath": "target-apps/meeting-assistant/db/sql",
            "designDocPath": "docs/design/meeting-assistant.md",
            "postgresMcpParams": {"db_endpoint": "db.example.com", "database": "sdlc_agentic_ai"},
            "seedMinRows": 5,
            "seedMaxRows": 10,
        },
        agent_result="### handoff_for_developer\n- DSN from env\n",
        rds_applied=True,
    )
    assert "Python 3.12" in md
    assert "meeting_assistant" in md
    assert "FastAPI" in md
    assert "RDS apply" in md
    assert "DSN from env" in md


def test_write_db_handoff_creates_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import _shared.db_handoff as mod

    app_dir = tmp_path / "target-apps" / "demo-app" / "db" / "sql"
    app_dir.mkdir(parents=True)
    (app_dir / "001_init.sql").write_text("SELECT 1;", encoding="utf-8")
    monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)
    rel = write_db_handoff(
        "demo-app",
        {"dbOutputDir": "target-apps/demo-app/db", "preferredSqlPath": "target-apps/demo-app/db/sql"},
    )
    assert rel == "target-apps/demo-app/db/HANDOFF.md"
    assert (tmp_path / rel).is_file()
