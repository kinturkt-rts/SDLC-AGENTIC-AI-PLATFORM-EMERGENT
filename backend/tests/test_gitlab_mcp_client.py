"""Tests for GitLab MCP client transport selection (no network)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from _shared.gitlab_mcp_client import (  # noqa: E402
    gitlab_mcp_http_headers,
    gitlab_mcp_http_url,
    normalize_gitlab_mcp_http_url,
)


def test_gitlab_mcp_http_url_empty_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITLAB_MCP_HTTP_URL", raising=False)
    assert gitlab_mcp_http_url() is None


def test_normalize_gitlab_mcp_http_url_appends_mcp() -> None:
    assert (
        normalize_gitlab_mcp_http_url("http://gitlab-mcp.internal:8080")
        == "http://gitlab-mcp.internal:8080/mcp"
    )
    assert (
        normalize_gitlab_mcp_http_url("http://gitlab-mcp.internal:8080/mcp")
        == "http://gitlab-mcp.internal:8080/mcp"
    )


def test_gitlab_mcp_http_headers_include_token_and_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITLAB_PERSONAL_ACCESS_TOKEN", "glpat-test")
    monkeypatch.setenv("GITLAB_URL", "https://code.junodev.net")
    headers = gitlab_mcp_http_headers()
    assert headers["PRIVATE-TOKEN"] == "glpat-test"
    assert headers["GITLAB-URL"] == "https://code.junodev.net"


def test_gitlab_mcp_http_headers_omit_gitlab_url_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITLAB_TOKEN", "glpat-test")
    monkeypatch.setenv("GITLAB_MCP_SEND_GITLAB_URL", "false")
    headers = gitlab_mcp_http_headers()
    assert "GITLAB-URL" not in headers
