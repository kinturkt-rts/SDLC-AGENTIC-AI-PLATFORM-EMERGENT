"""Publish SDLC feature artifacts to GitLab via jmrplens MCP (same server as Cursor)."""

from __future__ import annotations

import asyncio
from typing import Any

from .github_publish import collect_feature_artifact_paths, default_branch_name, repo_root, slugify_feature
from .gitlab_api import gitlab_base_branch, gitlab_personal_access_token, gitlab_project_path
from .gitlab_jmrplens_mcp import (
    GitLabMcpError,
    call_gitlab_mcp_tool,
    gitlab_mcp_session,
    list_existing_blob_paths,
)

_BATCH_SIZE = 20


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
