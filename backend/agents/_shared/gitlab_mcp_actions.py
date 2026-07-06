"""GitLab MCP actions: env config, CLI helpers, and SDLC publish workflow."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Literal

from .gitlab_mcp_client import (
    GitLabMcpError,
    _list_repository_tree_async,
    call_gitlab_mcp_tool,
    gitlab_mcp_session,
    gitlab_mcp_url_candidates,
    gitlab_mcp_uses_cloudfront,
    list_existing_blob_paths,
    use_gitlab_mcp_http,
    using_gitlab_mcp_url,
)

_DEFAULT_API_URL = "https://code.junodev.net/api/v4"
_DEFAULT_PROJECT_PATH = "junolabs/sdlc-agentic-ai-platform/sdlc-agentic-ai-platform"
_DEFAULT_APPS_PROJECT_PATH = "junolabs/sdlc-agentic-ai-platform/sdlc-agentic-ai-platform-apps"
_BATCH_SIZE = 20
_HTTP_FILE_API_HINT = (
    "CloudFront/WAF returned 403 on the MCP POST body. "
    "Set GITLAB_MCP_HTTP_DIRECT_URL to the ALB /mcp URL (see config/agentcore/gitlab-mcp-endpoints.json)."
)

_WAF_LOCALHOST_HTTP = re.compile(r"https?://localhost(?=[:/])", re.IGNORECASE)


def sanitize_publish_content_for_waf(content: str) -> str:
    """Replace substrings that commonly trigger CloudFront/WAF on MCP POST bodies."""
    if not gitlab_mcp_uses_cloudfront():
        return content

    def _replace(match: re.Match[str]) -> str:
        scheme = match.group(0).split("://", 1)[0].lower()
        return f"{scheme}://127.0.0.1"

    return _WAF_LOCALHOST_HTTP.sub(_replace, content)


def _publish_batch_size() -> int:
    """HTTP MCP behind CloudFront/WAF: one file per request avoids body-size and content rules."""
    if use_gitlab_mcp_http():
        raw = os.getenv("GITLAB_MCP_HTTP_BATCH_SIZE", "1").strip()
        try:
            return max(1, int(raw))
        except ValueError:
            return 1
    return _BATCH_SIZE

PublishLayout = Literal["monorepo", "apps"]

_EXCLUDE_DIR_NAMES = frozenset(
    {".venv", "__pycache__", ".pytest_cache", "node_modules", ".git"}
)
_EXCLUDE_FILE_NAMES = frozenset({".env", ".coverage"})


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def slugify_feature(feature: str) -> str:
    return feature.strip().lower().replace("_", "-")


def should_include_file(path: Path) -> bool:
    if path.name in _EXCLUDE_FILE_NAMES:
        return False
    if path.suffix in {".pyc", ".pyo"}:
        return False
    return not any(part in _EXCLUDE_DIR_NAMES for part in path.parts)


def _load_developer_handoff_written_paths(slug: str, root: Path) -> list[str]:
    """Return monorepo-relative paths listed in developer-handoff.json."""
    candidates = (
        root / slug / "handoffs" / "developer-handoff.json",
        root / "agents" / "pipeline" / f"{slug}.developer-handoff.json",
    )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        written = data.get("writtenFiles") or []
        return [item for item in written if isinstance(item, str) and item.strip()]
    return []


def _workspace_source_for_repo_rel(slug: str, root: Path, repo_rel: str) -> Path | None:
    """Resolve a materialized workspace file for a monorepo-relative target-apps path."""
    normalized = repo_rel.replace("\\", "/").lstrip("/")
    prefix = f"target-apps/{slug}/"
    candidates: list[Path] = []
    if normalized.startswith(prefix):
        tail = normalized[len(prefix) :]
        candidates.append(root / slug / tail)
    candidates.append(root / normalized)
    for candidate in candidates:
        if candidate.is_file() and should_include_file(candidate):
            return candidate
    return None


def _entry_for_workspace_file(slug: str, root: Path, source: Path) -> tuple[str, str] | None:
    """Map a workspace file to (source_rel, gitlab_dest_rel)."""
    try:
        workspace_rel = source.relative_to(root).as_posix()
    except ValueError:
        return None
    if is_cloud_materialized_workspace(root, slug):
        dest = cloud_workspace_to_gitlab_dest(slug, workspace_rel)
        if not dest:
            return None
        return workspace_rel, dest
    return workspace_rel, workspace_rel


def _merge_developer_handoff_entries(
    slug: str,
    root: Path,
    entries: set[tuple[str, str]],
) -> None:
    """Include developer-handoff writtenFiles so late S3 writes are not dropped."""
    for repo_rel in _load_developer_handoff_written_paths(slug, root):
        source = _workspace_source_for_repo_rel(slug, root, repo_rel)
        if source is None:
            continue
        mapped = _entry_for_workspace_file(slug, root, source)
        if mapped:
            entries.add(mapped)


def is_cloud_materialized_workspace(root: Path, slug: str) -> bool:
    """True when *root* is a materialized S3 run dir (``<slug>/...``), not local monorepo."""
    if (root / "target-apps" / slug).is_dir():
        return False
    return (root / slug).is_dir()


def cloud_workspace_to_gitlab_dest(slug: str, workspace_rel: str) -> str | None:
    """Map a materialized cloud artifact path to monorepo GitLab destination path."""
    normalized = workspace_rel.replace("\\", "/").lstrip("/")
    prefix = f"{slug}/"
    if not normalized.startswith(prefix):
        return None
    tail = normalized[len(prefix) :]
    if not tail or tail.startswith("inputs/") or tail.startswith("telemetry/"):
        return None

    if tail == "context.json":
        return f"agents/pipeline/{slug}.context.json"

    if tail.startswith("handoffs/"):
        handoff_map = {
            "developer-handoff.json": f"agents/pipeline/{slug}.developer-handoff.json",
            "gitlab-handoff.json": f"agents/pipeline/{slug}.gitlab-handoff.json",
            "qa-handoff.json": f"agents/pipeline/{slug}.qa-handoff.json",
            "devops-handoff.json": f"agents/pipeline/{slug}.devops-handoff.json",
        }
        return handoff_map.get(Path(tail).name)

    if tail.startswith("docs/PRD/") or tail.startswith("docs/design/"):
        return tail

    if tail.startswith("docs/generated-diagrams/"):
        return tail

    if tail.startswith("docs/diagrams/"):
        return f"docs/generated-diagrams/{Path(tail).name}"

    return f"target-apps/{slug}/{tail}"


def collect_feature_artifact_entries(
    feature: str,
    *,
    root: Path | None = None,
) -> list[tuple[str, str]]:
    """Return ``(workspace_source_rel, gitlab_dest_rel)`` pairs to publish."""
    root = root or repo_root()
    slug = slugify_feature(feature)

    if is_cloud_materialized_workspace(root, slug):
        entries: set[tuple[str, str]] = set()
        cloud_root = root / slug
        for file_path in cloud_root.rglob("*"):
            if not file_path.is_file() or not should_include_file(file_path):
                continue
            source = file_path.relative_to(root).as_posix()
            dest = cloud_workspace_to_gitlab_dest(slug, source)
            if dest:
                entries.add((source, dest))
        _merge_developer_handoff_entries(slug, root, entries)
        return sorted(entries, key=lambda item: item[1])

    entries = {
        (rel, rel)
        for rel in _collect_local_monorepo_artifact_paths(feature, root=root)
    }
    _merge_developer_handoff_entries(slug, root, entries)
    return sorted(entries, key=lambda item: item[1])


def collect_feature_artifact_paths(feature: str, *, root: Path | None = None) -> list[str]:
    """Return repo-relative GitLab destination paths for one SDLC feature."""
    return [dest for _, dest in collect_feature_artifact_entries(feature, root=root)]


def _collect_local_monorepo_artifact_paths(feature: str, *, root: Path | None = None) -> list[str]:
    """Local monorepo layout: ``target-apps/<slug>/``, ``docs/PRD/``, pipeline handoffs."""
    root = root or repo_root()
    slug = slugify_feature(feature)
    rel_paths: set[str] = set()

    app_dir = root / "target-apps" / slug
    if app_dir.is_dir():
        for file_path in app_dir.rglob("*"):
            if file_path.is_file() and should_include_file(file_path):
                rel_paths.add(file_path.relative_to(root).as_posix())

    for candidate in (
        root / "docs" / "PRD" / f"{slug}.md",
        root / "docs" / "design" / f"{slug}.md",
        root / "docs" / "generated-diagrams" / f"{slug}.png",
        root / "docs" / "diagrams" / "generated-diagrams" / f"{slug}.png",
        root / "agents" / "pipeline" / f"{slug}.context.json",
        root / "agents" / "pipeline" / f"{slug}.developer-handoff.json",
        root / "agents" / "pipeline" / f"{slug}.qa-handoff.json",
        root / "agents" / "pipeline" / f"{slug}.devops-handoff.json",
        root / "agents" / "pipeline" / f"{slug}.gitlab-handoff.json",
    ):
        if candidate.is_file():
            rel_paths.add(candidate.relative_to(root).as_posix())

    return sorted(rel_paths)


def default_branch_name(feature: str) -> str:
    return f"sdlc/{slugify_feature(feature)}"


def apps_branch_name(feature: str) -> str:
    """Branch name for sdlc-agentic-ai-platform-apps (one branch per app, no sdlc/ prefix)."""
    return slugify_feature(feature)


def dest_path_for_apps_repo(rel_path: str, slug: str) -> str | None:
    """Map target-apps/<slug>/... to repo-root paths for the apps GitLab project."""
    prefix = f"target-apps/{slug}/"
    if rel_path.startswith(prefix):
        return rel_path[len(prefix) :]
    return None


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


def gitlab_apps_project_path() -> str:
    return (os.getenv("GITLAB_APPS_PROJECT_PATH") or _DEFAULT_APPS_PROJECT_PATH).strip()


def _mcp_error_message(exc: BaseException) -> str:
    """Extract a useful message from GitLabMcpError or nested ExceptionGroup wrappers."""
    if isinstance(exc, GitLabMcpError):
        return str(exc)
    if isinstance(exc, BaseExceptionGroup):
        for nested in exc.exceptions:
            msg = _mcp_error_message(nested)
            if msg and msg != str(exc):
                return msg
    message = str(exc)
    if "403 Forbidden" in message and "cloudfront.net/mcp" in message.lower():
        return f"{message}\n\n{_HTTP_FILE_API_HINT}"
    return message


def _is_branch_not_found(exc: BaseException) -> bool:
    message = _mcp_error_message(exc).lower()
    return "branch" in message and "not found" in message


def _run(coro: Any) -> dict[str, Any]:
    try:
        return asyncio.run(coro)
    except BaseException as exc:
        return {"ok": False, "error": _mcp_error_message(exc)}


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


def _batch_files(files: list[dict[str, str]], batch_size: int | None = None) -> list[list[dict[str, str]]]:
    size = batch_size if batch_size is not None else _publish_batch_size()
    return [files[i : i + size] for i in range(0, len(files), size)]


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
    for source_rel, dest_rel in collect_feature_artifact_entries(slug, root=root_path):
        if dest_rel.endswith(".devops-handoff.json"):
            continue
        src = root_path / source_rel
        data = src.read_bytes()
        if src.suffix.lower() == ".png":
            import base64

            content = base64.b64encode(data).decode("ascii")
        elif src.name == ".gitignore" or src.suffix.lower() in text_suffixes:
            content = sanitize_publish_content_for_waf(data.decode("utf-8"))
        else:
            import base64

            content = base64.b64encode(data).decode("ascii")
        files.append({"path": dest_rel, "content": content, "binary": src.suffix.lower() == ".png"})
    return files


def _collect_apps_repo_publish_files(feature: str, *, root: Any | None = None) -> list[dict[str, str]]:
    """Publish only target-apps/<slug>/ files at branch root (apps GitLab project)."""
    root_path = root or repo_root()
    slug = slugify_feature(feature)
    text_suffixes = {".py", ".md", ".sql", ".txt", ".ini", ".json", ".example"}
    files: list[dict[str, str]] = []
    for source_rel, dest_rel in collect_feature_artifact_entries(slug, root=root_path):
        dest = dest_path_for_apps_repo(dest_rel, slug)
        if dest is None:
            continue
        src = root_path / source_rel
        data = src.read_bytes()
        if src.suffix.lower() == ".png":
            import base64

            content = base64.b64encode(data).decode("ascii")
        elif src.name == ".gitignore" or src.suffix.lower() in text_suffixes:
            content = sanitize_publish_content_for_waf(data.decode("utf-8"))
        else:
            import base64

            content = base64.b64encode(data).decode("ascii")
        files.append({"path": dest, "content": content, "binary": src.suffix.lower() == ".png"})
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


async def _publish_files_via_file_api(
    session: Any,
    *,
    project_id: str,
    branch: str,
    slug: str,
    files: list[dict[str, str]],
    existing_paths: set[str],
) -> list[str]:
    """Upload one file per MCP call (required for HTTP MCP behind restrictive WAF)."""
    commit_ids: list[str] = []
    for item in files:
        path = item["path"].lstrip("/")
        tool = "gitlab_file_update" if path in existing_paths else "gitlab_file_create"
        payload: dict[str, Any] = {
            "project_id": project_id,
            "file_path": path,
            "branch": branch,
            "commit_message": _publish_commit_message(slug),
        }
        if item.get("binary"):
            payload["content"] = item["content"]
            payload["encoding"] = "base64"
        else:
            payload["content"] = item["content"]
        result = await call_gitlab_mcp_tool(session, tool, payload)
        existing_paths.add(path)
        commit_id = result.get("id") or result.get("short_id") or result.get("commit_id")
        if commit_id:
            commit_ids.append(str(commit_id))
    return commit_ids


async def _publish_text_file_batches(
    session: Any,
    *,
    project_id: str,
    branch: str,
    slug: str,
    text_files: list[dict[str, str]],
    existing_paths: set[str],
) -> list[str]:
    if use_gitlab_mcp_http():
        return await _publish_files_via_file_api(
            session,
            project_id=project_id,
            branch=branch,
            slug=slug,
            files=text_files,
            existing_paths=existing_paths,
        )

    commit_ids: list[str] = []
    batches = _batch_files(text_files)
    for index, batch in enumerate(batches, start=1):
        message = _publish_commit_message(slug, batch=index, total=len(batches))
        commit_result = await call_gitlab_mcp_tool(
            session,
            "gitlab_commit_create",
            {
                "project_id": project_id,
                "branch": branch,
                "commit_message": message,
                "actions": _commit_actions(batch, existing_paths),
            },
        )
        for item in batch:
            existing_paths.add(item["path"].lstrip("/"))
        commit_id = commit_result.get("id") or commit_result.get("short_id")
        if commit_id:
            commit_ids.append(str(commit_id))
    return commit_ids


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


def _publish_commit_message(slug: str, *, batch: int | None = None, total: int | None = None) -> str:
    if batch is not None and total is not None and total > 1:
        return f"feat({slug}): SDLC pipeline output (batch {batch}/{total})"
    return f"feat({slug}): SDLC pipeline output"


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
    return await _publish_files_via_file_api(
        session,
        project_id=project_id,
        branch=branch,
        slug=slug,
        files=binary_files,
        existing_paths=existing_paths,
    )


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
    except (GitLabMcpError, BaseExceptionGroup) as exc:
        if not _is_branch_not_found(exc):
            raise
        await call_gitlab_mcp_tool(
            session,
            "gitlab_branch_create",
            {"project_id": project_id, "branch_name": branch, "ref": base_branch},
        )
    return await list_existing_blob_paths(session, project_id=project_id, ref=branch)


def _publish_error(
    slug: str,
    publish_branch: str,
    cfg: dict[str, str],
    exc: BaseException,
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": _mcp_error_message(exc),
        "targetApp": slug,
        "branch": publish_branch,
        "gitlabProject": cfg["project"],
        "gitlabBaseBranch": cfg["base"],
    }


def _is_cloudfront_waf_403(exc: BaseException) -> bool:
    message = _mcp_error_message(exc).lower()
    return "403 forbidden" in message and "cloudfront.net/mcp" in message


def _empty_publish_diagnostic(slug: str, *, root: Path) -> str:
    """Hint why file collection returned nothing (S3 layout vs monorepo layout)."""
    cloud = is_cloud_materialized_workspace(root, slug)
    local_app = (root / "target-apps" / slug).is_dir()
    cloud_app = (root / slug).is_dir()
    entries = len(collect_feature_artifact_entries(slug, root=root))
    parts = [
        f" workspace={root}",
        f"cloud_layout={cloud}",
        f"has_target_apps={local_app}",
        f"has_slug_root={cloud_app}",
        f"mapped_entries={entries}",
    ]
    if cloud_app and not local_app and entries == 0:
        parts.append(
            "hint=cloud S3 tree present but no paths mapped; redeploy gitlab_agent with latest _shared/gitlab_mcp_actions.py"
        )
    elif not cloud_app and not local_app:
        parts.append("hint=materialized workspace empty or wrong runId; check ARTIFACT_STORE=s3 and S3 IAM on runtime")
    return " (" + ", ".join(parts) + ")"


async def publish_feature_async(
    feature: str,
    *,
    project: str | None = None,
    base_branch: str | None = None,
    branch: str | None = None,
    draft_mr: bool = False,
    open_mr: bool = False,
    root: Any | None = None,
    layout: PublishLayout = "monorepo",
) -> dict[str, Any]:
    """Push feature artifacts via jmrplens MCP (gitlab_commit_create); MR is opt-in."""
    gitlab_personal_access_token()
    root_path = root or repo_root()
    slug = slugify_feature(feature)
    cfg = gitlab_repo_config(project=project, base_branch=base_branch)
    if layout == "apps":
        publish_branch = (branch or apps_branch_name(slug)).strip()
        files = _collect_apps_repo_publish_files(slug, root=root_path)
    else:
        publish_branch = (branch or publish_branch_name(slug)).strip()
        files = _collect_monorepo_publish_files(slug, root=root_path)
    project_id = cfg["project"]

    if not files:
        detail = _empty_publish_diagnostic(slug, root=root_path)
        return {
            "ok": False,
            "error": f"No publishable artifacts found for '{slug}'{detail}",
            "targetApp": slug,
            "branch": publish_branch,
            **cfg,
        }

    commits: list[str] = []
    project_web_url: str | None = None
    mr_result: dict[str, Any] = {}

    async def _run_publish(session: Any) -> None:
        nonlocal project_web_url, mr_result
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
        commits.extend(
            await _publish_text_file_batches(
                session,
                project_id=project_id,
                branch=publish_branch,
                slug=slug,
                text_files=text_files,
                existing_paths=existing_paths,
            )
        )

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

    mcp_urls = gitlab_mcp_url_candidates() if use_gitlab_mcp_http() else []
    attempt_urls: list[str | None] = mcp_urls if mcp_urls else [None]
    last_exc: BaseException | None = None

    for index, mcp_url in enumerate(attempt_urls):
        try:
            if mcp_url:
                async with using_gitlab_mcp_url(mcp_url):
                    async with gitlab_mcp_session() as session:
                        await _run_publish(session)
            else:
                async with gitlab_mcp_session() as session:
                    await _run_publish(session)
            break
        except (GitLabMcpError, BaseExceptionGroup) as exc:
            last_exc = exc
            has_fallback = index < len(attempt_urls) - 1
            if not (_is_cloudfront_waf_403(exc) and has_fallback):
                return _publish_error(slug, publish_branch, cfg, exc)
    else:
        if last_exc is not None:
            return _publish_error(slug, publish_branch, cfg, last_exc)
        return _publish_error(slug, publish_branch, cfg, GitLabMcpError("GitLab MCP publish failed"))

    mr_url = str(mr_result.get("web_url") or "")
    branch_url = _branch_tree_url(project_web_url, publish_branch) if project_web_url else None
    return {
        "ok": True,
        "status": "published",
        "targetApp": slug,
        "branch": publish_branch,
        "gitlabProject": cfg["project"],
        "gitlabBaseBranch": cfg["base"],
        "publishLayout": layout,
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
    layout: PublishLayout = "monorepo",
) -> dict[str, Any]:
    return _run(
        publish_feature_async(
            feature,
            project=project,
            base_branch=base_branch,
            branch=branch,
            draft_mr=draft_mr,
            open_mr=open_mr,
            root=root,
            layout=layout,
        )
    )
