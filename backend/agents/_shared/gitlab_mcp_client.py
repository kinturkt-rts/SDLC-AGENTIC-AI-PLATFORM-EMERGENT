"""Call jmrplens/gitlab-mcp-server from agents (stdio locally or HTTP on AWS)."""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import urljoin, urlparse

from mcp import ClientSession, StdioServerParameters, stdio_client

_REPO_ROOT = Path(__file__).resolve().parents[2]


class GitLabMcpError(RuntimeError):
    """Raised when a jmrplens MCP tool returns isError."""


def gitlab_mcp_http_url() -> str | None:
    """Remote MCP endpoint, e.g. http://gitlab-mcp.internal:8080/mcp (AgentCore / ECS)."""
    raw = os.getenv("GITLAB_MCP_HTTP_URL", "").strip()
    return raw or None


def _gitlab_instance_url() -> str:
    explicit = os.getenv("GITLAB_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    api = os.getenv("GITLAB_API_URL", "").strip().rstrip("/")
    if api.endswith("/api/v4"):
        return api[: -len("/api/v4")]
    return "https://code.junodev.net"


def _gitlab_token() -> str:
    token = (
        os.getenv("GITLAB_PERSONAL_ACCESS_TOKEN", "").strip()
        or os.getenv("GITLAB_TOKEN", "").strip()
        or os.getenv("GL_TOKEN", "").strip()
    )
    if not token:
        raise GitLabMcpError(
            "Set GITLAB_PERSONAL_ACCESS_TOKEN or GITLAB_TOKEN for GitLab MCP HTTP/stdio."
        )
    return token


def gitlab_mcp_http_headers() -> dict[str, str]:
    """Per-request auth for HTTP mode (token not baked into the MCP server image)."""
    headers = {"PRIVATE-TOKEN": _gitlab_token()}
    if os.getenv("GITLAB_MCP_SEND_GITLAB_URL", "true").strip().lower() not in {
        "0",
        "false",
        "no",
    }:
        headers["GITLAB-URL"] = _gitlab_instance_url()
    return headers


def normalize_gitlab_mcp_http_url(url: str) -> str:
    """Ensure jmrplens Streamable HTTP path (/mcp) is present."""
    trimmed = url.strip().rstrip("/")
    if trimmed.endswith("/mcp"):
        return trimmed
    parsed = urlparse(trimmed)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid GITLAB_MCP_HTTP_URL: {url!r}")
    return urljoin(f"{parsed.scheme}://{parsed.netloc}/", "mcp")


def _mcp_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("TOOL_SURFACE", "individual")
    return env


def _server_params() -> StdioServerParameters:
    python = os.environ.get("GITLAB_MCP_PYTHON", sys.executable)
    return StdioServerParameters(
        command=python,
        args=[str(_REPO_ROOT / "scripts" / "gitlab_mcp_server.py")],
        env=_mcp_env(),
    )


def _parse_tool_result(result: Any) -> dict[str, Any]:
    if result.isError:
        parts: list[str] = []
        for block in result.content or []:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        raise GitLabMcpError("; ".join(parts) or "GitLab MCP tool failed")
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            return {"raw": text}
    return {}


@asynccontextmanager
async def gitlab_mcp_session() -> AsyncIterator[ClientSession]:
    """MCP session — stdio (local binary) or Streamable HTTP (shared ECS service)."""
    http_url = gitlab_mcp_http_url()
    if http_url:
        from mcp.client.streamable_http import streamablehttp_client

        url = normalize_gitlab_mcp_http_url(http_url)
        headers = gitlab_mcp_http_headers()
        async with streamablehttp_client(url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
        return

    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def call_gitlab_mcp_tool(
    session: ClientSession,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    result = await session.call_tool(tool_name, arguments=arguments)
    return _parse_tool_result(result)


async def _list_repository_tree_async(
    session: ClientSession,
    *,
    project_id: str,
    ref: str,
) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    page = 1
    while True:
        data = await call_gitlab_mcp_tool(
            session,
            "gitlab_repository_tree",
            {
                "project_id": project_id,
                "ref": ref,
                "recursive": True,
                "per_page": 100,
                "page": page,
            },
        )
        for entry in data.get("tree") or []:
            path = entry.get("path")
            entry_type = entry.get("type")
            if path and entry_type:
                entries.append({"path": str(path), "type": str(entry_type)})
        pagination = data.get("pagination") or {}
        if not pagination.get("has_more"):
            break
        page = int(pagination.get("next_page") or page + 1)
    return entries


async def list_existing_blob_paths(
    session: ClientSession,
    *,
    project_id: str,
    ref: str,
) -> set[str]:
    """List file paths on a branch (for create vs update commit actions)."""
    entries = await _list_repository_tree_async(session, project_id=project_id, ref=ref)
    return {entry["path"] for entry in entries if entry["type"] == "blob"}
