#!/usr/bin/env python3
"""Deprecated custom FastMCP GitLab server — use jmrplens/gitlab-mcp-server in Cursor.

gitlab-agent pipeline publish uses agents/_shared/gitlab_api.py (REST), not this file.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.gitlab_api import (  # noqa: E402
    GitLabApiError,
    create_merge_request as api_create_merge_request,
    create_merge_request_note as api_create_merge_request_note,
    gitlab_api_url,
    gitlab_base_branch,
    gitlab_personal_access_token,
    gitlab_project_path,
    push_files as api_push_files,
    verify_connection,
)
from _shared.gitlab_mcp_publish import publish_feature_async  # noqa: E402

load_dotenv(_REPO_ROOT / ".env")
load_dotenv(_REPO_ROOT / ".env.local")

os.environ.setdefault("FASTMCP_STATELESS_HTTP", "true")

mcp = FastMCP("GitLab MCP Server")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=gitlab_api_url(),
        timeout=httpx.Timeout(60.0, connect=15.0),
    )


def _project_id(project: Optional[str]) -> str:
    return (project or gitlab_project_path()).strip()


@mcp.tool()
async def gitlab_verify_connection(project: Optional[str] = None) -> dict:
    """Verify GitLab API credentials and project access."""
    try:
        gitlab_personal_access_token()
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    try:
        async with _client() as client:
            info = await verify_connection(client, project=_project_id(project))
        return {"ok": True, "api_url": gitlab_api_url(), **info}
    except GitLabApiError as exc:
        return {"ok": False, "error": str(exc), "details": exc.details}
    except httpx.RequestError as exc:
        return {"ok": False, "error": f"Network error: {exc}"}


@mcp.tool()
async def push_files(
    branch: str,
    message: str,
    files: list[dict[str, str]],
    project: Optional[str] = None,
    base_branch: Optional[str] = None,
) -> dict:
    """
    Commit one or more files to a GitLab branch (create branch from base if missing).

    Each file: {"path": "relative/path", "content": "text or base64"}.
    Compatible with the GitHub MCP push_files shape used by github-agent.
    """
    if not branch or not message:
        return {"error": "branch and message are required"}
    if not files:
        return {"error": "files must be a non-empty list"}

    try:
        gitlab_personal_access_token()
        async with _client() as client:
            result = await api_push_files(
                client,
                project=_project_id(project),
                branch=branch,
                message=message,
                files=files,
                base_branch=base_branch or gitlab_base_branch(),
            )
        return {"ok": True, **result}
    except GitLabApiError as exc:
        return {"ok": False, "error": str(exc), "details": exc.details}
    except httpx.RequestError as exc:
        return {"ok": False, "error": f"Network error: {exc}"}


@mcp.tool()
async def create_merge_request(
    source_branch: str,
    title: str,
    target_branch: Optional[str] = None,
    description: str = "",
    project: Optional[str] = None,
    draft: bool = False,
    remove_source_branch: bool = False,
) -> dict:
    """Open a GitLab merge request (MR)."""
    if not source_branch or not title:
        return {"error": "source_branch and title are required"}
    try:
        gitlab_personal_access_token()
        async with _client() as client:
            result = await api_create_merge_request(
                client,
                project=_project_id(project),
                source_branch=source_branch,
                target_branch=target_branch or gitlab_base_branch(),
                title=title,
                description=description,
                draft=draft,
                remove_source_branch=remove_source_branch,
            )
        return {"ok": True, **result, "url": result.get("web_url")}
    except GitLabApiError as exc:
        return {"ok": False, "error": str(exc), "details": exc.details}
    except httpx.RequestError as exc:
        return {"ok": False, "error": f"Network error: {exc}"}


@mcp.tool()
async def create_merge_request_note(
    merge_request_iid: int,
    body: str,
    project: Optional[str] = None,
) -> dict:
    """Post a comment on a GitLab merge request (used by qa-agent)."""
    if merge_request_iid < 1 or not body.strip():
        return {"error": "merge_request_iid and body are required"}
    try:
        gitlab_personal_access_token()
        async with _client() as client:
            result = await api_create_merge_request_note(
                client,
                project=_project_id(project),
                merge_request_iid=merge_request_iid,
                body=body,
            )
        return {"ok": True, **result}
    except GitLabApiError as exc:
        return {"ok": False, "error": str(exc), "details": exc.details}
    except httpx.RequestError as exc:
        return {"ok": False, "error": f"Network error: {exc}"}


@mcp.tool()
async def publish_feature(
    target_app: str,
    project: Optional[str] = None,
    base_branch: Optional[str] = None,
    branch: Optional[str] = None,
    draft_mr: bool = False,
    open_mr: bool = False,
) -> dict:
    """Push SDLC pipeline artifacts to sdlc/<app> (reused per app); MR to main is opt-in."""
    try:
        return await publish_feature_async(
            target_app,
            project=project,
            base_branch=base_branch,
            branch=branch,
            draft_mr=draft_mr,
            open_mr=open_mr,
            root=_REPO_ROOT,
        )
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Self-hosted GitLab MCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default=os.environ.get("GITLAB_MCP_TRANSPORT", "stdio"),
    )
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    args = parser.parse_args()

    if args.transport == "streamable-http":
        print(f"Starting GitLab MCP on http://{args.host}:{args.port} (streamable-http)")
        print(f"API: {gitlab_api_url()}")
        print(f"Project: {gitlab_project_path()}")
        print("Tools: gitlab_verify_connection, push_files, create_merge_request,")
        print("       create_merge_request_note, publish_feature")
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
