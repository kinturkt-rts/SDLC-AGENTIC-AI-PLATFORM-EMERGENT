"""Tests for shared GitLab MCP platform endpoint config."""

from __future__ import annotations

import json
from pathlib import Path


def test_gitlab_mcp_endpoints_config_has_direct_and_cloudfront_urls() -> None:
    path = Path(__file__).resolve().parents[1] / "config" / "agentcore" / "gitlab-mcp-endpoints.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    direct = data["directMcpUrl"]
    cloudfront = data["cloudFront"]["mcpUrl"]
    assert direct.endswith("/mcp")
    assert cloudfront.endswith("/mcp")
    assert "cloudfront.net" in cloudfront
    assert data["usage"]["gitlabAgentPublish"] == "cloudFront.mcpUrl"
