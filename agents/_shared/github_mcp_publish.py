"""Publish SDLC feature artifacts via GitHub MCP (@modelcontextprotocol/server-github)."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from mcp import ClientSession, StdioServerParameters, stdio_client

from .github_publish import (
    collect_showcase_publish_files,
    github_feature_branch,
    repo_root,
    slugify_feature,
)
from .mcp_clients import github_personal_access_token

_DEFAULT_OWNER = "kinturkt-rts"
_DEFAULT_REPO = "SDLC-Agentic-AI-Platform"
_BATCH_SIZE = 20


def github_repo_config(
    *,
    owner: str | None = None,
    repo: str | None = None,
    base_branch: str | None = None,
) -> dict[str, str]:
    """Resolve GitHub target repo from args or environment."""
    return {
        "owner": (owner or os.getenv("GITHUB_OWNER", _DEFAULT_OWNER)).strip(),
        "repo": (repo or os.getenv("GITHUB_REPO", _DEFAULT_REPO)).strip(),
        "base": (base_branch or os.getenv("GITHUB_BASE_BRANCH", "main")).strip() or "main",
    }


def _parse_mcp_tool_result(result: Any) -> dict[str, Any]:
    if result.isError:
        parts: list[str] = []
        for block in result.content or []:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        raise RuntimeError("; ".join(parts) or "GitHub MCP tool failed")
    for block in result.content or []:
        text = getattr(block, "text", None)
        if not text:
            continue
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {"raw": text}
    return {}


def _iter_exceptions(exc: BaseException) -> list[BaseException]:
    """Flatten ExceptionGroup chains into a list of leaf exceptions."""
    if isinstance(exc, BaseExceptionGroup):
        out: list[BaseException] = []
        for sub in exc.exceptions:
            out.extend(_iter_exceptions(sub))
        return out
    return [exc]


def _exception_message(exc: BaseException) -> str:
    parts = [str(e) for e in _iter_exceptions(exc)]
    return "; ".join(parts) if parts else str(exc)


async def _call_github_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    token = github_personal_access_token()
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={**os.environ, "GITHUB_PERSONAL_ACCESS_TOKEN": token},
    )
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)
                return _parse_mcp_tool_result(result)
    except BaseException as exc:
        message = _exception_message(exc)
        if "Bad credentials" in message or "Authentication Failed" in message:
            raise RuntimeError(
                "GitHub authentication failed. Set GITHUB_PERSONAL_ACCESS_TOKEN in .env.local "
                "(a classic PAT or fine-grained token with repo scope). "
                "Note: github-agent uses @modelcontextprotocol/server-github via npx — "
                "not the Cursor GitHub Copilot MCP URL in mcp.json."
            ) from exc
        if "Not Found" in message:
            raise RuntimeError(
                f"GitHub MCP {tool_name} failed: {message}. "
                "Check GITHUB_OWNER/GITHUB_REPO and that the token can write to the repo."
            ) from exc
        raise RuntimeError(f"GitHub MCP {tool_name} failed: {message}") from exc


def _github_branch_exists(cfg: dict[str, str], branch: str) -> bool:
    """Check remote branch via GitHub REST (avoids create_branch 422 when branch exists)."""
    token = github_personal_access_token()
    url = (
        f"https://api.github.com/repos/{cfg['owner']}/{cfg['repo']}"
        f"/git/ref/heads/{urllib.parse.quote(branch, safe='')}"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "sdlc-github-agent",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise RuntimeError(
            f"GitHub branch lookup failed ({exc.code}): {exc.reason}"
        ) from exc


async def _ensure_feature_branch(cfg: dict[str, str], branch: str) -> None:
    """Create feature branch from base when missing (legacy server-github does not auto-create)."""
    if _github_branch_exists(cfg, branch):
        return
    try:
        await _call_github_mcp_tool(
            "create_branch",
            {
                "owner": cfg["owner"],
                "repo": cfg["repo"],
                "branch": branch,
                "from_branch": cfg["base"],
            },
        )
    except RuntimeError as exc:
        msg = str(exc).lower()
        if "reference already exists" in msg or "already exists" in msg:
            return
        raise


def _batch_files(files: list[dict[str, str]], batch_size: int = _BATCH_SIZE) -> list[list[dict[str, str]]]:
    return [files[i : i + batch_size] for i in range(0, len(files), batch_size)]


def _pr_body(slug: str, paths: list[str]) -> str:
    lines = "\n".join(f"- `{p}`" for p in paths[:40])
    extra = f"\n- … and {len(paths) - 40} more" if len(paths) > 40 else ""
    return (
        f"Automated SDLC pipeline output for **{slug}**.\n\n"
        f"## Artifacts\n{lines}{extra}\n\n"
        f"## Docs\n"
        f"- [PRD](docs/PRD/{slug}.md)\n"
        f"- [Design](docs/design/{slug}.md)\n"
    )


async def mcp_publish_feature_async(
    feature: str,
    *,
    owner: str | None = None,
    repo: str | None = None,
    base_branch: str | None = None,
    draft_pr: bool = False,
    root: Any | None = None,
) -> dict[str, Any]:
    """Push feature artifacts to GitHub via MCP push_files, then create_pull_request."""
    root_path = root or repo_root()
    slug = slugify_feature(feature)
    cfg = github_repo_config(owner=owner, repo=repo, base_branch=base_branch)
    branch = github_feature_branch(slug)

    files = collect_showcase_publish_files(slug, root=root_path)
    if not files:
        return {
            "ok": False,
            "error": f"No publishable artifacts found for '{slug}'",
            "targetApp": slug,
            "branch": branch,
            **cfg,
        }

    batches = _batch_files(files)
    commits: list[str] = []
    await _ensure_feature_branch(cfg, branch)
    for index, batch in enumerate(batches, start=1):
        message = f"feat({slug}): SDLC pipeline output (batch {index}/{len(batches)})"
        push_result = await _call_github_mcp_tool(
            "push_files",
            {
                "owner": cfg["owner"],
                "repo": cfg["repo"],
                "branch": branch,
                "message": message,
                "files": [{"path": f["path"], "content": f["content"]} for f in batch],
            },
        )
        commit_sha = (
            push_result.get("object", {}).get("sha")
            if isinstance(push_result.get("object"), dict)
            else push_result.get("sha")
        )
        if commit_sha:
            commits.append(str(commit_sha))

    pr_title = f"feat({slug}): SDLC pipeline output"
    pr_args: dict[str, Any] = {
        "owner": cfg["owner"],
        "repo": cfg["repo"],
        "title": pr_title,
        "head": branch,
        "base": cfg["base"],
        "body": _pr_body(slug, [f["path"] for f in files]),
    }
    if draft_pr:
        pr_args["draft"] = True

    pr_result = await _call_github_mcp_tool("create_pull_request", pr_args)
    pr_url = str(pr_result.get("url", ""))
    pr_number = pr_result.get("number") or pr_result.get("pullRequestNumber")
    if pr_number is None and "/pull/" in pr_url:
        try:
            pr_number = int(pr_url.rstrip("/").split("/")[-1])
        except ValueError:
            pr_number = None

    paths_published = [f["path"] for f in files]
    return {
        "ok": True,
        "status": "published",
        "targetApp": slug,
        "branch": branch,
        "githubOwner": cfg["owner"],
        "githubRepo": cfg["repo"],
        "githubBaseBranch": cfg["base"],
        "pathsPublished": paths_published,
        "commits": commits,
        "pullRequestUrl": pr_url or None,
        "pullRequestNumber": pr_number,
        "repoUrl": f"https://github.com/{cfg['owner']}/{cfg['repo']}",
        "branchUrl": f"https://github.com/{cfg['owner']}/{cfg['repo']}/tree/{branch}",
    }


def mcp_publish_feature(
    feature: str,
    *,
    owner: str | None = None,
    repo: str | None = None,
    base_branch: str | None = None,
    draft_pr: bool = False,
    root: Any | None = None,
) -> dict[str, Any]:
    """Synchronous wrapper for mcp_publish_feature_async."""
    return asyncio.run(
        mcp_publish_feature_async(
            feature,
            owner=owner,
            repo=repo,
            base_branch=base_branch,
            draft_pr=draft_pr,
            root=root,
        )
    )
