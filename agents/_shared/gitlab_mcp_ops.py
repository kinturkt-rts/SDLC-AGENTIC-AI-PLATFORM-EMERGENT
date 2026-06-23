"""GitLab MCP read/write helpers (jmrplens): projects, branch files, MR notes."""

from __future__ import annotations

import asyncio
from typing import Any

from .gitlab_api import gitlab_personal_access_token, gitlab_project_path
from .gitlab_jmrplens_mcp import (
    GitLabMcpError,
    _list_repository_tree_async,
    call_gitlab_mcp_tool,
    gitlab_mcp_session,
)


async def list_projects_async(
    *,
    project_id: str | None = None,
    membership: bool = True,
    page: int = 1,
    per_page: int = 20,
) -> dict[str, Any]:
    """List GitLab projects visible to the authenticated user."""
    gitlab_personal_access_token()
    project = (project_id or gitlab_project_path()).strip()
    async with gitlab_mcp_session() as session:
        data = await call_gitlab_mcp_tool(
            session,
            "gitlab_project_list",
            {
                "membership": membership,
                "page": page,
                "per_page": per_page,
            },
        )
        projects = data.get("projects") or data.get("items") or []
        return {
            "ok": True,
            "projects": projects,
            "pagination": data.get("pagination"),
            "scopeProject": project,
        }


async def list_branch_files_async(
    *,
    branch: str,
    project_id: str | None = None,
    blobs_only: bool = False,
) -> dict[str, Any]:
    """List repository tree entries on a branch (files and folders)."""
    ref = branch.strip()
    if not ref:
        return {"ok": False, "error": "branch is required"}

    gitlab_personal_access_token()
    project = (project_id or gitlab_project_path()).strip()

    async with gitlab_mcp_session() as session:
        entries = await _list_repository_tree_async(session, project_id=project, ref=ref)
        if blobs_only:
            entries = [entry for entry in entries if entry["type"] == "blob"]
        return {
            "ok": True,
            "project": project,
            "branch": ref,
            "entries": entries,
            "count": len(entries),
        }


async def list_mr_notes_async(
    *,
    mr_iid: int,
    project_id: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict[str, Any]:
    """List top-level notes (comments) on a merge request."""
    gitlab_personal_access_token()
    project = (project_id or gitlab_project_path()).strip()
    async with gitlab_mcp_session() as session:
        data = await call_gitlab_mcp_tool(
            session,
            "gitlab_mr_notes_list",
            {
                "project_id": project,
                "merge_request_iid": mr_iid,
                "page": page,
                "per_page": per_page,
            },
        )
        notes = data.get("notes") or data.get("items") or []
        return {
            "ok": True,
            "project": project,
            "mrIid": mr_iid,
            "notes": notes,
            "pagination": data.get("pagination"),
        }


async def create_mr_note_async(
    *,
    mr_iid: int,
    body: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Add a comment to a merge request."""
    text = body.strip()
    if not text:
        return {"ok": False, "error": "comment body is required"}

    gitlab_personal_access_token()
    project = (project_id or gitlab_project_path()).strip()

    async with gitlab_mcp_session() as session:
        note = await call_gitlab_mcp_tool(
            session,
            "gitlab_mr_note_create",
            {
                "project_id": project,
                "merge_request_iid": mr_iid,
                "body": text,
            },
        )
        return {
            "ok": True,
            "project": project,
            "mrIid": mr_iid,
            "note": note,
        }


def _run(coro: Any) -> dict[str, Any]:
    try:
        return asyncio.run(coro)
    except GitLabMcpError as exc:
        return {"ok": False, "error": str(exc)}
    except BaseExceptionGroup as exc:
        for nested in exc.exceptions:
            if isinstance(nested, GitLabMcpError):
                return {"ok": False, "error": str(nested)}
        return {"ok": False, "error": str(exc)}


def list_projects(**kwargs: Any) -> dict[str, Any]:
    return _run(list_projects_async(**kwargs))


def list_branch_files(**kwargs: Any) -> dict[str, Any]:
    return _run(list_branch_files_async(**kwargs))


def list_mr_notes(**kwargs: Any) -> dict[str, Any]:
    return _run(list_mr_notes_async(**kwargs))


def create_mr_note(**kwargs: Any) -> dict[str, Any]:
    return _run(create_mr_note_async(**kwargs))
