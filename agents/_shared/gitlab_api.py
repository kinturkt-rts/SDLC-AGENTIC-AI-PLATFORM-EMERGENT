"""GitLab REST API helpers for the self-hosted GitLab MCP server and agents."""

from __future__ import annotations

import base64
import os
from typing import Any
from urllib.parse import quote

import httpx

_DEFAULT_API_URL = "https://code.junodev.net/api/v4"
_DEFAULT_PROJECT_PATH = "junolabs/sdlc-agentic-ai-platform/sdlc-agentic-ai-platform"
_BATCH_SIZE = 20


class GitLabApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def gitlab_personal_access_token() -> str:
    for key in ("GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_TOKEN", "GL_TOKEN"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    raise ValueError(
        "GITLAB_PERSONAL_ACCESS_TOKEN is not set. Add a GitLab PAT to .env "
        "(scopes: api, read_api, read_repository, write_repository)."
    )


def gitlab_api_url() -> str:
    return (os.getenv("GITLAB_API_URL") or _DEFAULT_API_URL).strip().rstrip("/")


def gitlab_project_path() -> str:
    return (
        os.getenv("GITLAB_PROJECT_PATH")
        or os.getenv("GITLAB_PROJECT_ID")
        or _DEFAULT_PROJECT_PATH
    ).strip()


def gitlab_base_branch() -> str:
    return (os.getenv("GITLAB_BASE_BRANCH") or "main").strip() or "main"


def encode_project_id(project: str) -> str:
    project = project.strip()
    if project.isdigit():
        return project
    return quote(project, safe="")


def _headers() -> dict[str, str]:
    return {
        "PRIVATE-TOKEN": gitlab_personal_access_token(),
        "Content-Type": "application/json",
    }


def _raise_for_status(response: httpx.Response, context: str) -> None:
    if response.is_success:
        return
    detail: Any
    try:
        detail = response.json()
    except Exception:
        detail = response.text
    raise GitLabApiError(
        f"{context}: HTTP {response.status_code}",
        status_code=response.status_code,
        details=detail,
    )


async def verify_connection(
    client: httpx.AsyncClient,
    *,
    project: str | None = None,
) -> dict[str, Any]:
    project_ref = encode_project_id(project or gitlab_project_path())
    response = await client.get(f"/projects/{project_ref}", headers=_headers())
    _raise_for_status(response, "GitLab project lookup failed")
    data = response.json()
    return {
        "id": data.get("id"),
        "path_with_namespace": data.get("path_with_namespace"),
        "web_url": data.get("web_url"),
        "default_branch": data.get("default_branch"),
    }


async def branch_exists(
    client: httpx.AsyncClient,
    *,
    project: str,
    branch: str,
) -> bool:
    project_ref = encode_project_id(project)
    response = await client.get(
        f"/projects/{project_ref}/repository/branches/{quote(branch, safe='')}",
        headers=_headers(),
    )
    if response.status_code == 404:
        return False
    _raise_for_status(response, f"Branch lookup failed for {branch}")
    return True


async def ensure_branch(
    client: httpx.AsyncClient,
    *,
    project: str,
    branch: str,
    ref: str | None = None,
) -> dict[str, Any]:
    if await branch_exists(client, project=project, branch=branch):
        return {"branch": branch, "created": False}
    project_ref = encode_project_id(project)
    payload = {"branch": branch, "ref": ref or gitlab_base_branch()}
    response = await client.post(
        f"/projects/{project_ref}/repository/branches",
        headers=_headers(),
        json=payload,
    )
    _raise_for_status(response, f"Create branch failed for {branch}")
    return {"branch": branch, "created": True, "ref": payload["ref"]}


async def file_action_for_path(
    client: httpx.AsyncClient,
    *,
    project: str,
    branch: str,
    file_path: str,
) -> str:
    project_ref = encode_project_id(project)
    encoded_path = quote(file_path, safe="")
    response = await client.get(
        f"/projects/{project_ref}/repository/files/{encoded_path}",
        headers=_headers(),
        params={"ref": branch},
    )
    if response.status_code == 404:
        return "create"
    _raise_for_status(response, f"File lookup failed for {file_path}")
    return "update"


def _commit_actions_for_files(
    files: list[dict[str, str]],
    *,
    actions: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    commit_actions: list[dict[str, str]] = []
    for item in files:
        path = item["path"].lstrip("/")
        content = item["content"]
        action = (actions or {}).get(path, item.get("action", "create"))
        entry: dict[str, str] = {
            "action": action,
            "file_path": path,
        }
        try:
            raw = base64.b64decode(content, validate=True)
            if b"\x00" in raw[:8192]:
                entry["content"] = content
                entry["encoding"] = "base64"
            else:
                entry["content"] = raw.decode("utf-8")
        except Exception:
            entry["content"] = content
        commit_actions.append(entry)
    return commit_actions


async def create_commit(
    client: httpx.AsyncClient,
    *,
    project: str,
    branch: str,
    message: str,
    files: list[dict[str, str]],
    resolve_actions: bool = True,
) -> dict[str, Any]:
    project_ref = encode_project_id(project)
    actions_map: dict[str, str] = {}
    if resolve_actions:
        for item in files:
            path = item["path"].lstrip("/")
            actions_map[path] = await file_action_for_path(
                client, project=project, branch=branch, file_path=path
            )
    payload = {
        "branch": branch,
        "commit_message": message,
        "actions": _commit_actions_for_files(files, actions=actions_map),
    }
    response = await client.post(
        f"/projects/{project_ref}/repository/commits",
        headers=_headers(),
        json=payload,
    )
    _raise_for_status(response, "Create commit failed")
    data = response.json()
    return {
        "id": data.get("id"),
        "short_id": data.get("short_id"),
        "title": data.get("title"),
        "web_url": data.get("web_url"),
    }


async def push_files(
    client: httpx.AsyncClient,
    *,
    project: str,
    branch: str,
    message: str,
    files: list[dict[str, str]],
    base_branch: str | None = None,
) -> dict[str, Any]:
    await ensure_branch(
        client,
        project=project,
        branch=branch,
        ref=base_branch or gitlab_base_branch(),
    )
    commits: list[dict[str, Any]] = []
    for index in range(0, len(files), _BATCH_SIZE):
        batch = files[index : index + _BATCH_SIZE]
        batch_no = index // _BATCH_SIZE + 1
        total_batches = (len(files) + _BATCH_SIZE - 1) // _BATCH_SIZE
        batch_message = message
        if total_batches > 1:
            batch_message = f"{message} (batch {batch_no}/{total_batches})"
        commit = await create_commit(
            client,
            project=project,
            branch=branch,
            message=batch_message,
            files=batch,
        )
        commits.append(commit)
    return {
        "branch": branch,
        "commits": commits,
        "commit_count": len(commits),
        "latest_sha": commits[-1].get("id") if commits else None,
    }


async def create_merge_request(
    client: httpx.AsyncClient,
    *,
    project: str,
    source_branch: str,
    target_branch: str | None = None,
    title: str,
    description: str = "",
    draft: bool = False,
    remove_source_branch: bool = False,
) -> dict[str, Any]:
    project_ref = encode_project_id(project)
    payload = {
        "source_branch": source_branch,
        "target_branch": target_branch or gitlab_base_branch(),
        "title": title,
        "description": description,
        "remove_source_branch": remove_source_branch,
    }
    if draft:
        payload["title"] = f"Draft: {title}"
    response = await client.post(
        f"/projects/{project_ref}/merge_requests",
        headers=_headers(),
        json=payload,
    )
    _raise_for_status(response, "Create merge request failed")
    data = response.json()
    return {
        "iid": data.get("iid"),
        "id": data.get("id"),
        "web_url": data.get("web_url"),
        "title": data.get("title"),
        "state": data.get("state"),
        "source_branch": data.get("source_branch"),
        "target_branch": data.get("target_branch"),
    }


async def create_merge_request_note(
    client: httpx.AsyncClient,
    *,
    project: str,
    merge_request_iid: int,
    body: str,
) -> dict[str, Any]:
    project_ref = encode_project_id(project)
    response = await client.post(
        f"/projects/{project_ref}/merge_requests/{merge_request_iid}/notes",
        headers=_headers(),
        json={"body": body},
    )
    _raise_for_status(response, "Create merge request note failed")
    data = response.json()
    return {
        "id": data.get("id"),
        "body": data.get("body"),
        "web_url": data.get("web_url"),
    }
