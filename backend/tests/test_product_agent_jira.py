"""Tests for opt-in Jira backlog wiring on product-agent (AgentCore + local)."""

from __future__ import annotations

import base64
import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENT_PATH = _REPO_ROOT / "agents" / "product-agent" / "product_agent.py"


def _load_agent_module():
    spec = importlib.util.spec_from_file_location("product_agent_jira", _AGENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {_AGENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(_REPO_ROOT / "agents"))
    spec.loader.exec_module(module)
    return module


def test_atlassian_basic_auth_from_email_and_token(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    monkeypatch.delenv("ATLASSIAN_MCP_BASIC_AUTH", raising=False)
    monkeypatch.setenv("ATLASSIAN_MCP_EMAIL", "dev@example.com")
    monkeypatch.setenv("ATLASSIAN_MCP_TOKEN", "secret-token")
    expected = base64.b64encode(b"dev@example.com:secret-token").decode("ascii")
    assert mod._atlassian_mcp_basic_auth_value() == expected


def test_atlassian_mcp_url_uses_token_endpoint_when_basic_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    monkeypatch.delenv("ATLASSIAN_MCP_URL", raising=False)
    monkeypatch.setenv("ATLASSIAN_MCP_BASIC_AUTH", "abc123")
    assert mod._atlassian_mcp_url() == mod.ATLASSIAN_MCP_TOKEN_URL


def test_atlassian_mcp_remote_args_include_auth_header(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    monkeypatch.setenv("ATLASSIAN_MCP_BASIC_AUTH", "encoded")
    args = mod._atlassian_mcp_remote_args()
    assert "mcp-remote@latest" in args[1]
    assert "--header" in args
    assert args[-1] == "Authorization: Basic encoded"


def test_jira_backlog_requested_from_context(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    monkeypatch.setenv("AGENTCORE_AGENT", "product-agent")
    monkeypatch.setenv("AGENTCORE_PRODUCT_SKIP_JIRA", "false")
    ok, project = mod._jira_backlog_requested(
        {"createJiraBacklog": True, "jiraProjectKey": "saap"},
        task="Create PRD",
    )
    assert ok is True
    assert project == "SAAP"


def test_jira_backlog_blocked_when_agentcore_skip_true(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    monkeypatch.setenv("AGENTCORE_AGENT", "product-agent")
    monkeypatch.setenv("AGENTCORE_PRODUCT_SKIP_JIRA", "true")
    ok, _ = mod._jira_backlog_requested(
        {"createJiraBacklog": True, "jiraProjectKey": "SAAP"},
        task="Create PRD",
    )
    assert ok is False


def test_options_from_dict_parses_with_jira_camel_case() -> None:
    from _shared.sdlc_pipeline import options_from_dict

    opts = options_from_dict(
        {
            "target_app": "demo-app",
            "withJira": True,
            "jiraProject": "HAWKAI",
        }
    )
    assert opts.with_jira is True
    assert opts.jira_project == "HAWKAI"
