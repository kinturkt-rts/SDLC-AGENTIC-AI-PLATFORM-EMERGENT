"""Call jmrplens/gitlab-mcp-server from agents (same binary as Cursor MCP)."""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from mcp import ClientSession, StdioServerParameters, stdio_client

_REPO_ROOT = Path(__file__).resolve().parents[2]


class GitLabMcpError(RuntimeError):
    """Raised when a jmrplens MCP tool returns isError."""


def _mcp_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("TOOL_SURFACE", "individual")
    return env


def _server_params() -> StdioServerParameters:
    python = os.environ.get("GITLAB_MCP_PYTHON", sys.executable)
    return StdioServerParameters(
        command=python,
        args=[str(_REPO_ROOT / "scripts" / "gitlab_jmrplens_stdio.py")],
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
    """One MCP session per publish run (avoids repeated process startup)."""
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
