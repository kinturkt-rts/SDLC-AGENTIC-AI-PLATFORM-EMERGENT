"""Tests for database-agent Postgres MCP context enrichment."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENT_PATH = _REPO_ROOT / "agents" / "database-agent" / "database_agent.py"


def _load_agent_module():
    sys.modules.pop("database_agent", None)
    spec = importlib.util.spec_from_file_location("database_agent", _AGENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {_AGENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(_REPO_ROOT / "agents"))
    spec.loader.exec_module(module)
    return module


def test_enrich_postgres_mcp_context_sets_apply_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """--with-postgres should inject params and post-run RDS apply in Context."""
    monkeypatch.setenv("POSTGRES_MCP_DB_ENDPOINT", "mydb.example.rds.amazonaws.com")
    monkeypatch.setenv("POSTGRES_MCP_DATABASE", "meeting_assistant")
    monkeypatch.setenv("POSTGRES_MCP_REGION", "us-east-2")
    monkeypatch.setenv("SEED_MIN_ROWS", "5")
    monkeypatch.setenv("SEED_MAX_ROWS", "10")

    mod = _load_agent_module()
    ctx: dict[str, Any] = {"targetApp": "meeting-assistant"}
    mod._enrich_postgres_mcp_context(ctx, use_postgres=True)

    assert ctx["applyToRdsAfterWrite"] is True
    assert ctx["seedMinRows"] == 5
    assert ctx["seedMaxRows"] == 10
    params = ctx["postgresMcpParams"]
    assert params["db_endpoint"] == "mydb.example.rds.amazonaws.com"
    assert params["database"] == "meeting_assistant"
    assert params["cluster_identifier"] == ""
    assert "postgresMcpWarning" not in ctx


def test_enrich_postgres_mcp_context_skipped_without_flag() -> None:
    """Files-only runs must not set applyToRdsAfterWrite."""
    mod = _load_agent_module()
    ctx: dict[str, Any] = {"targetApp": "meeting-assistant"}
    mod._enrich_postgres_mcp_context(ctx, use_postgres=False)

    assert "applyToRdsAfterWrite" not in ctx
    assert "postgresMcpParams" not in ctx
    assert "seedMinRows" in ctx
    assert "seedMaxRows" in ctx


def test_enrich_postgres_mcp_context_warns_on_missing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing POSTGRES_MCP_* env should surface a warning in Context."""
    monkeypatch.setenv("POSTGRES_MCP_DB_ENDPOINT", "")
    monkeypatch.setenv("POSTGRES_MCP_DATABASE", "")

    mod = _load_agent_module()
    ctx: dict[str, Any] = {}
    mod._enrich_postgres_mcp_context(ctx, use_postgres=True)

    assert ctx["applyToRdsAfterWrite"] is True
    assert "postgresMcpWarning" in ctx


def test_max_output_tokens_defaults_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    monkeypatch.delenv("DATABASE_AGENT_MAX_TOKENS", raising=False)
    monkeypatch.delenv("BEDROCK_MAX_OUTPUT_TOKENS", raising=False)
    assert mod._max_output_tokens() == 32768

    monkeypatch.setenv("DATABASE_AGENT_MAX_TOKENS", "65536")
    assert mod._max_output_tokens() == 65536
