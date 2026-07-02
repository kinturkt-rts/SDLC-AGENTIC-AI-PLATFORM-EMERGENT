"""Call jmrplens/gitlab-mcp-server via ECS HTTP MCP (CloudFront or ALB)."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import urljoin, urlparse

from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

_REPO_ROOT = Path(__file__).resolve().parents[2]

# HTTP ECS deployments default to dynamic tool surface (gitlab_execute_action).
# Local stdio uses individual tools (gitlab_project_list, …).
_INDIVIDUAL_TOOL_TO_DYNAMIC_ACTION: dict[str, str] = {
    "gitlab_project_list": "project.list",
    "gitlab_project_get": "project.get",
    "gitlab_repository_tree": "repository.tree",
    "gitlab_commit_create": "repository.commit_create",
    "gitlab_branch_get": "branch.get",
    "gitlab_branch_create": "branch.create",
    "gitlab_file_create": "repository.file_create",
    "gitlab_file_update": "repository.file_update",
    "gitlab_mr_create": "merge_request.create",
    "gitlab_mr_notes_list": "mr_review.note_list",
    "gitlab_mr_note_create": "mr_review.note_create",
}

_use_dynamic_actions: ContextVar[bool] = ContextVar("_use_dynamic_actions", default=False)
_forced_mcp_url: ContextVar[str | None] = ContextVar("_forced_mcp_url", default=None)


class GitLabMcpError(RuntimeError):
    """Raised when a jmrplens MCP tool returns isError."""


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
        os.getenv("GITLAB_TOKEN", "").strip()
        or os.getenv("GITLAB_PERSONAL_ACCESS_TOKEN", "").strip()
        or os.getenv("GL_TOKEN", "").strip()
    )
    if not token:
        raise GitLabMcpError(
            "Set GITLAB_TOKEN or GITLAB_PERSONAL_ACCESS_TOKEN for GitLab MCP."
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
        raise ValueError(f"Invalid GitLab MCP HTTP URL: {url!r}")
    return urljoin(f"{parsed.scheme}://{parsed.netloc}/", "mcp")


def _gitlab_mcp_http_url_env_keys() -> tuple[str, ...]:
    """Env keys in priority order (CloudFront canonical; direct ALB is fallback)."""
    return ("GITLAB_MCP_URL", "GITLAB_MCP_HTTP_URL", "GITLAB_MCP_HTTP_DIRECT_URL")


def gitlab_mcp_url_candidates() -> list[str]:
    """Distinct MCP HTTP URLs in priority order."""
    urls: list[str] = []
    seen: set[str] = set()
    for key in _gitlab_mcp_http_url_env_keys():
        raw = os.getenv(key, "").strip()
        if not raw:
            continue
        normalized = normalize_gitlab_mcp_http_url(raw)
        if normalized in seen:
            continue
        seen.add(normalized)
        urls.append(normalized)
    return urls


def _raw_gitlab_mcp_http_url() -> str | None:
    candidates = gitlab_mcp_url_candidates()
    return candidates[0] if candidates else None


def gitlab_mcp_url() -> str | None:
    """Remote Streamable HTTP MCP endpoint (CloudFront canonical, ALB fallback).

    Priority: GITLAB_MCP_URL / GITLAB_MCP_HTTP_URL (CloudFront) then
    GITLAB_MCP_HTTP_DIRECT_URL (ALB bypass when WAF blocks or env override).
    """
    forced = _forced_mcp_url.get()
    if forced:
        return forced
    return _raw_gitlab_mcp_http_url()


def gitlab_mcp_fallback_url() -> str | None:
    """Next MCP HTTP URL after the primary (usually ALB when CloudFront is primary)."""
    candidates = gitlab_mcp_url_candidates()
    return candidates[1] if len(candidates) > 1 else None


@asynccontextmanager
async def using_gitlab_mcp_url(url: str) -> AsyncIterator[None]:
    """Force MCP HTTP transport to a specific URL for one publish/session."""
    token = _forced_mcp_url.set(normalize_gitlab_mcp_http_url(url))
    try:
        yield
    finally:
        _forced_mcp_url.reset(token)


def gitlab_mcp_uses_cloudfront() -> bool:
    """True when the primary HTTP MCP URL is a CloudFront distribution."""
    forced = _forced_mcp_url.get()
    primary = forced if forced else _raw_gitlab_mcp_http_url()
    return bool(primary and "cloudfront.net" in primary.lower())


def gitlab_mcp_http_url() -> str | None:
    """Alias for gitlab_mcp_url() — matches ECS/AgentCore deploy naming."""
    return gitlab_mcp_url()


def use_gitlab_mcp_http() -> bool:
    return _raw_gitlab_mcp_http_url() is not None


def uses_dynamic_gitlab_tool_surface(tool_names: set[str]) -> bool:
    """True when server exposes gitlab_execute_action instead of individual tools."""
    return "gitlab_execute_action" in tool_names and "gitlab_project_list" not in tool_names


def dynamic_action_for_individual_tool(tool_name: str) -> str | None:
    return _INDIVIDUAL_TOOL_TO_DYNAMIC_ACTION.get(tool_name)


def _mcp_http_required_error() -> GitLabMcpError:
    return GitLabMcpError(
        "Set GITLAB_MCP_URL or GITLAB_MCP_HTTP_DIRECT_URL in .env.local "
        "(see config/agentcore/gitlab-mcp-endpoints.json)."
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
async def _http_gitlab_mcp_session_at(url: str) -> AsyncIterator[ClientSession]:
    headers = gitlab_mcp_http_headers()
    async with create_mcp_http_client(headers=headers) as client:
        async with streamable_http_client(url, http_client=client) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


@asynccontextmanager
async def _http_gitlab_mcp_session() -> AsyncIterator[ClientSession]:
    url = gitlab_mcp_url()
    if not url:
        raise GitLabMcpError("Set GITLAB_MCP_URL or GITLAB_MCP_HTTP_URL for HTTP GitLab MCP.")
    async with _http_gitlab_mcp_session_at(url) as session:
        yield session


async def _configure_tool_surface(session: ClientSession) -> None:
    tools = await session.list_tools()
    names = {tool.name for tool in tools.tools}
    _use_dynamic_actions.set(uses_dynamic_gitlab_tool_surface(names))


@asynccontextmanager
async def gitlab_mcp_session() -> AsyncIterator[ClientSession]:
    """One MCP session per publish run (ECS HTTP MCP)."""
    token = _use_dynamic_actions.set(False)
    try:
        if not use_gitlab_mcp_http():
            raise _mcp_http_required_error()
        async with _http_gitlab_mcp_session() as session:
            await _configure_tool_surface(session)
            yield session
    finally:
        _use_dynamic_actions.reset(token)


async def call_gitlab_mcp_tool(
    session: ClientSession,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    if _use_dynamic_actions.get():
        dynamic_action = dynamic_action_for_individual_tool(tool_name)
        if dynamic_action:
            result = await session.call_tool(
                "gitlab_execute_action",
                arguments={"action": dynamic_action, "params": arguments},
            )
            return _parse_tool_result(result)
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
