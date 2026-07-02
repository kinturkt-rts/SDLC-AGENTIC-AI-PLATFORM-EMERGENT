"""Call jmrplens/gitlab-mcp-server from agents (stdio locally or HTTP on ECS)."""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, AsyncIterator

from mcp import ClientSession, StdioServerParameters, stdio_client
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


class GitLabMcpError(RuntimeError):
    """Raised when a jmrplens MCP tool returns isError."""


def gitlab_mcp_url() -> str | None:
    """Remote Streamable HTTP MCP endpoint (e.g. ECS behind CloudFront)."""
    url = os.getenv("GITLAB_MCP_URL", "").strip().rstrip("/")
    return url or None


def gitlab_mcp_http_headers() -> dict[str, str]:
    """Headers required by the deployed jmrplens HTTP MCP server."""
    token = (
        os.getenv("GITLAB_TOKEN", "").strip()
        or os.getenv("GITLAB_PERSONAL_ACCESS_TOKEN", "").strip()
    )
    if not token:
        raise GitLabMcpError(
            "Set GITLAB_TOKEN or GITLAB_PERSONAL_ACCESS_TOKEN for GitLab MCP."
        )

    explicit = os.getenv("GITLAB_URL", "").strip().rstrip("/")
    if explicit:
        gitlab_url = explicit
    else:
        api = os.getenv("GITLAB_API_URL", "").strip().rstrip("/")
        if api.endswith("/api/v4"):
            gitlab_url = api[: -len("/api/v4")]
        else:
            gitlab_url = "https://code.junodev.net"

    return {
        "PRIVATE-TOKEN": token,
        "GITLAB-URL": gitlab_url,
    }


def use_gitlab_mcp_http() -> bool:
    return gitlab_mcp_url() is not None


def uses_dynamic_gitlab_tool_surface(tool_names: set[str]) -> bool:
    """True when server exposes gitlab_execute_action instead of individual tools."""
    return "gitlab_execute_action" in tool_names and "gitlab_project_list" not in tool_names


def dynamic_action_for_individual_tool(tool_name: str) -> str | None:
    return _INDIVIDUAL_TOOL_TO_DYNAMIC_ACTION.get(tool_name)


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
async def _stdio_gitlab_mcp_session() -> AsyncIterator[ClientSession]:
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


@asynccontextmanager
async def _http_gitlab_mcp_session() -> AsyncIterator[ClientSession]:
    url = gitlab_mcp_url()
    if not url:
        raise GitLabMcpError("GITLAB_MCP_URL is not set.")

    headers = gitlab_mcp_http_headers()
    async with create_mcp_http_client(headers=headers) as client:
        async with streamable_http_client(url, http_client=client) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


async def _configure_tool_surface(session: ClientSession) -> None:
    tools = await session.list_tools()
    names = {tool.name for tool in tools.tools}
    _use_dynamic_actions.set(uses_dynamic_gitlab_tool_surface(names))


@asynccontextmanager
async def gitlab_mcp_session() -> AsyncIterator[ClientSession]:
    """One MCP session per publish run (stdio locally, HTTP when GITLAB_MCP_URL is set)."""
    token = _use_dynamic_actions.set(False)
    try:
        if use_gitlab_mcp_http():
            async with _http_gitlab_mcp_session() as session:
                await _configure_tool_surface(session)
                yield session
        else:
            if not (_REPO_ROOT / "scripts" / "gitlab_mcp_server.py").is_file():
                raise GitLabMcpError("scripts/gitlab_mcp_server.py not found.")
            binary_candidates = (
                _REPO_ROOT / "bin" / "gitlab-mcp-server.exe",
                _REPO_ROOT / "bin" / "gitlab-mcp-server",
            )
            if not any(path.is_file() for path in binary_candidates):
                raise GitLabMcpError(
                    "Local GitLab MCP binary not found and GITLAB_MCP_URL is unset. "
                    "Add GITLAB_MCP_URL to .env.local for the ECS HTTP MCP, or run "
                    ".\\scripts\\install-jmrplens-gitlab-mcp.ps1 for local stdio."
                )
            async with _stdio_gitlab_mcp_session() as session:
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
