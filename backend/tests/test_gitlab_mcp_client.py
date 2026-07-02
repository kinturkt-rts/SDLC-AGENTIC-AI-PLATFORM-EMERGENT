"""Tests for GitLab MCP client transport selection (no network)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from _shared.gitlab_mcp_client import (  # noqa: E402
    GitLabMcpError,
    dynamic_action_for_individual_tool,
    gitlab_mcp_http_headers,
    gitlab_mcp_http_url,
    gitlab_mcp_url,
    gitlab_mcp_uses_cloudfront,
    normalize_gitlab_mcp_http_url,
    use_gitlab_mcp_http,
    uses_dynamic_gitlab_tool_surface,
)


def test_gitlab_mcp_url_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITLAB_MCP_URL", raising=False)
    monkeypatch.delenv("GITLAB_MCP_HTTP_URL", raising=False)
    monkeypatch.delenv("GITLAB_MCP_HTTP_DIRECT_URL", raising=False)
    assert gitlab_mcp_url() is None
    assert gitlab_mcp_http_url() is None
    assert use_gitlab_mcp_http() is False


def test_gitlab_mcp_http_direct_url_takes_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITLAB_MCP_URL", "https://example.cloudfront.net/mcp")
    monkeypatch.setenv(
        "GITLAB_MCP_HTTP_DIRECT_URL",
        "http://gitlab-mcp-alb-123.us-east-2.elb.amazonaws.com/mcp",
    )
    assert (
        gitlab_mcp_url()
        == "http://gitlab-mcp-alb-123.us-east-2.elb.amazonaws.com/mcp"
    )


def test_gitlab_mcp_url_strips_trailing_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITLAB_MCP_HTTP_DIRECT_URL", raising=False)
    monkeypatch.setenv("GITLAB_MCP_URL", "https://example.cloudfront.net/mcp/")
    assert gitlab_mcp_url() == "https://example.cloudfront.net/mcp"
    assert use_gitlab_mcp_http() is True


def test_gitlab_mcp_http_url_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITLAB_MCP_URL", raising=False)
    monkeypatch.delenv("GITLAB_MCP_HTTP_DIRECT_URL", raising=False)
    monkeypatch.setenv("GITLAB_MCP_HTTP_URL", "http://gitlab-mcp.internal:8080")
    assert gitlab_mcp_http_url() == "http://gitlab-mcp.internal:8080/mcp"
    assert use_gitlab_mcp_http() is True


def test_normalize_gitlab_mcp_http_url_appends_mcp() -> None:
    assert (
        normalize_gitlab_mcp_http_url("http://gitlab-mcp.internal:8080")
        == "http://gitlab-mcp.internal:8080/mcp"
    )
    assert (
        normalize_gitlab_mcp_http_url("http://gitlab-mcp.internal:8080/mcp")
        == "http://gitlab-mcp.internal:8080/mcp"
    )


def test_gitlab_mcp_http_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITLAB_PERSONAL_ACCESS_TOKEN", "glpat-test")
    monkeypatch.setenv("GITLAB_URL", "https://code.junodev.net")
    assert gitlab_mcp_http_headers() == {
        "PRIVATE-TOKEN": "glpat-test",
        "GITLAB-URL": "https://code.junodev.net",
    }


def test_gitlab_mcp_http_headers_derive_url_from_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITLAB_TOKEN", "glpat-test")
    monkeypatch.delenv("GITLAB_URL", raising=False)
    monkeypatch.setenv("GITLAB_API_URL", "https://gitlab.example.com/api/v4")
    headers = gitlab_mcp_http_headers()
    assert headers["PRIVATE-TOKEN"] == "glpat-test"
    assert headers["GITLAB-URL"] == "https://gitlab.example.com"


def test_gitlab_mcp_http_headers_omit_gitlab_url_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITLAB_TOKEN", "glpat-test")
    monkeypatch.setenv("GITLAB_MCP_SEND_GITLAB_URL", "false")
    headers = gitlab_mcp_http_headers()
    assert "GITLAB-URL" not in headers


def test_gitlab_mcp_http_headers_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("GITLAB_TOKEN", "GITLAB_PERSONAL_ACCESS_TOKEN", "GL_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(GitLabMcpError, match="GITLAB_TOKEN"):
        gitlab_mcp_http_headers()


def test_uses_dynamic_gitlab_tool_surface() -> None:
    assert uses_dynamic_gitlab_tool_surface({"gitlab_execute_action", "gitlab_find_action"}) is True
    assert uses_dynamic_gitlab_tool_surface({"gitlab_project_list", "gitlab_commit_create"}) is False


def test_dynamic_action_for_individual_tool() -> None:
    assert dynamic_action_for_individual_tool("gitlab_project_list") == "project.list"
    assert dynamic_action_for_individual_tool("gitlab_commit_create") == "repository.commit_create"
    assert dynamic_action_for_individual_tool("unknown_tool") is None


def test_publish_batch_size_smaller_for_http(monkeypatch: pytest.MonkeyPatch) -> None:
    from _shared.gitlab_mcp_actions import _batch_files, _publish_batch_size  # noqa: E402

    monkeypatch.delenv("GITLAB_MCP_HTTP_BATCH_SIZE", raising=False)
    monkeypatch.delenv("GITLAB_MCP_URL", raising=False)
    monkeypatch.delenv("GITLAB_MCP_HTTP_URL", raising=False)
    monkeypatch.delenv("GITLAB_MCP_HTTP_DIRECT_URL", raising=False)
    assert _publish_batch_size() == 20
    assert len(_batch_files([{"path": "a"}] * 5)) == 1

    monkeypatch.setenv("GITLAB_MCP_URL", "https://example.cloudfront.net/mcp")
    assert _publish_batch_size() == 1
    assert len(_batch_files([{"path": "a"}] * 5)) == 5


def test_gitlab_mcp_uses_cloudfront(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITLAB_MCP_URL", "https://d123.cloudfront.net/mcp")
    monkeypatch.delenv("GITLAB_MCP_HTTP_DIRECT_URL", raising=False)
    assert gitlab_mcp_uses_cloudfront() is True

    monkeypatch.setenv(
        "GITLAB_MCP_HTTP_DIRECT_URL",
        "http://gitlab-mcp-alb-123.us-east-2.elb.amazonaws.com/mcp",
    )
    assert gitlab_mcp_uses_cloudfront() is False
