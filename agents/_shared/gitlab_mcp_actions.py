"""GitLab MCP actions: env config, CLI helpers, and SDLC publish workflow."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from .github_publish import collect_feature_artifact_paths, default_branch_name, repo_root, slugify_feature
from .gitlab_mcp_client import (
    GitLabMcpError,
    _list_repository_tree_async,
    call_gitlab_mcp_tool,
    gitlab_mcp_session,
    list_existing_blob_paths,
)

_DEFAULT_API_URL = "https://code.junodev.net/api/v4"
_DEFAULT_PROJECT_PATH = "junolabs/sdlc-agentic-ai-platform/sdlc-agentic-ai-platform"
_BATCH_SIZE = 20


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


def _mcp_error_message(exc: BaseException) -> str | None:
    """Extract GitLabMcpError text from nested asyncio/ExceptionGroup wrappers."""
    if isinstance(exc, GitLabMcpError):
        return str(exc)
    if isinstance(exc, BaseExceptionGroup):
        for nested in exc.exceptions:
            msg = _mcp_error_message(nested)
            if msg:
                return msg
    return None


def _run(coro: Any) -> dict[str, Any]:
    try:
        return asyncio.run(coro)
    except BaseException as exc:
        msg = _mcp_error_message(exc)
        if msg:
            return {"ok": False, "error": msg}
        return {"ok": False, "error": str(exc)}


# --- Repo config & publish helpers ---


def publish_branch_name(feature: str) -> str:
    """One stable branch per target app; republishs update files on the same branch."""
    return default_branch_name(feature)


def _branch_tree_url(web_url: str, branch: str) -> str:
    base = web_url.rstrip("/")
    encoded = branch.replace("/", "%2F")
    return f"{base}/-/tree/{encoded}"


def gitlab_repo_config(
    *,
    project: str | None = None,
    base_branch: str | None = None,
) -> dict[str, str]:
    return {
        "project": (project or gitlab_project_path()).strip(),
        "base": (base_branch or gitlab_base_branch()).strip() or "main",
    }


def _batch_files(files: list[dict[str, str]], batch_size: int = _BATCH_SIZE) -> list[list[dict[str, str]]]:
    return [files[i : i + batch_size] for i in range(0, len(files), batch_size)]


def _mr_body(slug: str, paths: list[str]) -> str:
    lines = "\n".join(f"- `{p}`" for p in paths[:40])
    extra = f"\n- … and {len(paths) - 40} more" if len(paths) > 40 else ""
    return (
        f"Automated SDLC pipeline output for **{slug}**.\n\n"
        f"## Artifacts\n{lines}{extra}\n\n"
        f"## Docs\n"
        f"- [PRD](docs/PRD/{slug}.md)\n"
        f"- [Design](docs/design/{slug}.md)\n"
    )


def _collect_monorepo_publish_files(feature: str, *, root: Any | None = None) -> list[dict[str, str]]:
    root_path = root or repo_root()
    slug = slugify_feature(feature)
    text_suffixes = {".py", ".md", ".sql", ".txt", ".ini", ".json", ".example"}
    files: list[dict[str, str]] = []
    for rel in collect_feature_artifact_paths(slug, root=root_path):
        if rel.endswith(".devops-handoff.json"):
            continue
        src = root_path / rel
        data = src.read_bytes()
        if src.suffix.lower() == ".png":
            import base64

            content = base64.b64encode(data).decode("ascii")
        elif src.name == ".gitignore" or src.suffix.lower() in text_suffixes:
            content = data.decode("utf-8")
        else:
            import base64

            content = base64.b64encode(data).decode("ascii")
        files.append({"path": rel, "content": content, "binary": src.suffix.lower() == ".png"})
    return files


def _split_publish_files(files: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    text_files: list[dict[str, str]] = []
    binary_files: list[dict[str, str]] = []
    for item in files:
        if item.get("binary"):
            binary_files.append(item)
        else:
            text_files.append(item)
    return text_files, binary_files


def _commit_content(content: str) -> str:
    """GitLab requires content on create/update; jmrplens omits empty strings from JSON."""
    return content if content else "\n"


def _commit_actions(
    batch: list[dict[str, str]],
    existing_paths: set[str],
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for item in batch:
        path = item["path"].lstrip("/")
        actions.append(
            {
                "action": "update" if path in existing_paths else "create",
                "file_path": path,
                "content": _commit_content(item["content"]),
            }
        )
    return actions


# --- MCP tool actions (projects, branch files, MR notes) ---


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


def list_projects(**kwargs: Any) -> dict[str, Any]:
    return _run(list_projects_async(**kwargs))


def list_branch_files(**kwargs: Any) -> dict[str, Any]:
    return _run(list_branch_files_async(**kwargs))


def list_mr_notes(**kwargs: Any) -> dict[str, Any]:
    return _run(list_mr_notes_async(**kwargs))


def create_mr_note(**kwargs: Any) -> dict[str, Any]:
    return _run(create_mr_note_async(**kwargs))


# --- SDLC publish workflow ---


async def _publish_binary_files(
    session: Any,
    *,
    project_id: str,
    branch: str,
    slug: str,
    binary_files: list[dict[str, str]],
    existing_paths: set[str],
) -> list[str]:
    """jmrplens commit_create schema has no per-action encoding; use file_create/update."""
    commit_ids: list[str] = []
    for item in binary_files:
        path = item["path"].lstrip("/")
        tool = "gitlab_file_update" if path in existing_paths else "gitlab_file_create"
        result = await call_gitlab_mcp_tool(
            session,
            tool,
            {
                "project_id": project_id,
                "file_path": path,
                "branch": branch,
                "content": item["content"],
                "encoding": "base64",
                "commit_message": f"feat({slug}): add binary artifact {path}",
            },
        )
        existing_paths.add(path)
        commit_id = result.get("id") or result.get("short_id") or result.get("commit_id")
        if commit_id:
            commit_ids.append(str(commit_id))
    return commit_ids


async def _ensure_publish_branch(
    session: Any,
    *,
    project_id: str,
    branch: str,
    base_branch: str,
) -> set[str]:
    try:
        await call_gitlab_mcp_tool(
            session,
            "gitlab_branch_get",
            {"project_id": project_id, "branch_name": branch},
        )
    except GitLabMcpError:
        await call_gitlab_mcp_tool(
            session,
            "gitlab_branch_create",
            {"project_id": project_id, "branch_name": branch, "ref": base_branch},
        )
        return set()
    return await list_existing_blob_paths(session, project_id=project_id, ref=branch)


def _publish_error(
    slug: str,
    publish_branch: str,
    cfg: dict[str, str],
    exc: BaseException,
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": str(exc),
        "targetApp": slug,
        "branch": publish_branch,
        **cfg,
    }


async def publish_feature_async(
    feature: str,
    *,
    project: str | None = None,
    base_branch: str | None = None,
    branch: str | None = None,
    draft_mr: bool = False,
    open_mr: bool = False,
    root: Any | None = None,
) -> dict[str, Any]:
    """Push feature artifacts via jmrplens MCP (gitlab_commit_create); MR is opt-in."""
    gitlab_personal_access_token()
    root_path = root or repo_root()
    slug = slugify_feature(feature)
    cfg = gitlab_repo_config(project=project, base_branch=base_branch)
    publish_branch = (branch or publish_branch_name(slug)).strip()
    project_id = cfg["project"]

    files = _collect_monorepo_publish_files(slug, root=root_path)
    if not files:
        return {
            "ok": False,
            "error": f"No publishable artifacts found for '{slug}'",
            "targetApp": slug,
            "branch": publish_branch,
            **cfg,
        }

    commits: list[str] = []
    project_web_url: str | None = None
    mr_result: dict[str, Any] = {}

    try:
        async with gitlab_mcp_session() as session:
            project_info = await call_gitlab_mcp_tool(
                session,
                "gitlab_project_get",
                {"project_id": project_id},
            )
            project_web_url = str(project_info.get("web_url") or "").strip() or None

            existing_paths = await _ensure_publish_branch(
                session,
                project_id=project_id,
                branch=publish_branch,
                base_branch=cfg["base"],
            )

            text_files, binary_files = _split_publish_files(files)
            batches = _batch_files(text_files)
            for index, batch in enumerate(batches, start=1):
                message = f"feat({slug}): SDLC pipeline output (batch {index}/{len(batches)})"
                commit_result = await call_gitlab_mcp_tool(
                    session,
                    "gitlab_commit_create",
                    {
                        "project_id": project_id,
                        "branch": publish_branch,
                        "commit_message": message,
                        "actions": _commit_actions(batch, existing_paths),
                    },
                )
                for item in batch:
                    existing_paths.add(item["path"].lstrip("/"))
                commit_id = commit_result.get("id") or commit_result.get("short_id")
                if commit_id:
                    commits.append(str(commit_id))

            commits.extend(
                await _publish_binary_files(
                    session,
                    project_id=project_id,
                    branch=publish_branch,
                    slug=slug,
                    binary_files=binary_files,
                    existing_paths=existing_paths,
                )
            )

            if open_mr:
                title = f"feat({slug}): SDLC pipeline output"
                if draft_mr:
                    title = f"Draft: {title}"
                mr_result = await call_gitlab_mcp_tool(
                    session,
                    "gitlab_mr_create",
                    {
                        "project_id": project_id,
                        "source_branch": publish_branch,
                        "target_branch": cfg["base"],
                        "title": title,
                        "description": _mr_body(slug, [f["path"] for f in files]),
                    },
                )
    except GitLabMcpError as exc:
        return _publish_error(slug, publish_branch, cfg, exc)
    except BaseExceptionGroup as exc:
        for nested in exc.exceptions:
            if isinstance(nested, GitLabMcpError):
                return _publish_error(slug, publish_branch, cfg, nested)
        return _publish_error(slug, publish_branch, cfg, exc)

    mr_url = str(mr_result.get("web_url") or "")
    branch_url = _branch_tree_url(project_web_url, publish_branch) if project_web_url else None
    return {
        "ok": True,
        "status": "published",
        "targetApp": slug,
        "branch": publish_branch,
        "gitlabProject": cfg["project"],
        "gitlabBaseBranch": cfg["base"],
        "openMergeRequest": open_mr,
        "pathsPublished": [f["path"] for f in files],
        "commits": commits,
        "mergeRequestUrl": mr_url or None,
        "mergeRequestIid": mr_result.get("iid"),
        "repoUrl": project_web_url,
        "branchUrl": branch_url,
    }


def publish_feature(
    feature: str,
    *,
    project: str | None = None,
    base_branch: str | None = None,
    branch: str | None = None,
    draft_mr: bool = False,
    open_mr: bool = False,
    root: Any | None = None,
) -> dict[str, Any]:
    return asyncio.run(
        publish_feature_async(
            feature,
            project=project,
            base_branch=base_branch,
            branch=branch,
            draft_mr=draft_mr,
            open_mr=open_mr,
            root=root,
        )
    )
