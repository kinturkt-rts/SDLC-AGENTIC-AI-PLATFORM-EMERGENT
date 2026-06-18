"""DevOps agent — Strands + git publish tools + optional GitHub MCP + A2A.

Publishes SDLC feature artifacts to a git branch, opens a GitHub pull request,
and hands off PR metadata to qa-agent for review comments.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(_REPO_ROOT / "agents"))
from _shared.context_cli import load_context_extra, parse_context_args
from _shared.env import load_repo_env
from _shared.github_publish import (
    collect_feature_artifact_paths,
    default_branch_name,
    gh_create_pull_request,
    git_publish_feature,
    slugify_feature,
)
from _shared.mcp_clients import MCP_FACTORIES, github_personal_access_token
from _shared.pipeline_context import (
    TargetAppRequiredError,
    enrich_handoff_context,
    resolve_cli_context,
    resolve_target_app,
)

load_repo_env()
os.environ.setdefault("BYPASS_TOOL_CONSENT", "true")

import botocore.config
from a2a.types import AgentSkill
from strands import Agent
from strands.models import BedrockModel
from strands.multiagent.a2a import A2AServer
from strands.tools.decorator import tool

AGENT_NAME = "devops-agent"
A2A_PORT = 9105

DEFAULT_PIPELINE_TASK = """\
Publish SDLC outputs for targetApp to GitHub (mirrors developer opening a PR).

**Step 1 — inventory**
1a. devops_list_publish_paths(targetApp) — confirm files to ship (app, PRD, design, handoffs).
1b. Read developerHandoffPath from Context when set.

**Step 2 — git branch + push (deterministic)**
2a. devops_git_publish(targetApp) — creates/updates branch sdlc/<targetApp>, commits artifacts, pushes.
2b. If ok=false, report error and stop.

**Step 3 — open pull request**
3a. When githubOwner + githubRepo are in Context (or GITHUB_OWNER/GITHUB_REPO env):
    - Prefer `gh` via devops_create_pull_request when GITHUB_USE_GH_CLI is not "false".
    - Otherwise use GitHub MCP `create_pull_request` with head=branch, base=githubBaseBranch (default main).
3b. PR title: `feat(<targetApp>): SDLC pipeline output`
3b. PR body: bullet list of paths published, link to PRD/design, pytest command from developer handoff.

**Step 4 — handoff for qa-agent**
Reply with sections:
1. **status** — published | skipped | failed
2. **branch** — git branch name
3. **pull_request** — url and number (if created)
4. **paths_published** — list
5. **handoff_json** — fenced ```json with keys:
   targetApp, status, branch, pullRequestUrl, pullRequestNumber, githubOwner, githubRepo,
   githubBaseBranch, pathsPublished, qaNextStep ("Run qa-agent with same context to test and comment on PR")

Do not modify application source code. Do not commit .env files.
"""

DEVOPS_SYS_PROMPT = """\
You are the DevOps Agent for the Autonomous SDLC platform. You run **after developer-agent**
(and optional local pytest verify), **before qa-agent** — mirroring a developer pushing a feature branch.

## Your job

1. Collect pipeline artifacts for `targetApp` (FastAPI app, PRD, design, diagram, handoff JSON).
2. Commit them on branch `sdlc/<targetApp>` and push to `origin` (monorepo workflow).
3. Open a GitHub pull request when `githubOwner` + `githubRepo` are configured.
4. Emit structured **handoff_json** so qa-agent can run tests locally and post results on the PR.

## Tools

| Tool | Use |
|------|-----|
| `devops_list_publish_paths` | List repo-relative paths that will be committed |
| `devops_git_publish` | git checkout -B, add, commit, push (never stages .env) |
| `devops_create_pull_request` | Create PR via `gh` CLI when available |
| GitHub MCP | Fallback `create_pull_request`, `push_files` for separate repos |

## QA handoff (real SDLC mirror)

- **Developer-agent** wrote code under `target-apps/<service>/`.
- **You** publish that branch + open PR — like `git push` + "Open pull request".
- **qa-agent** runs pytest on the **same local checkout** (fast, no clone) and posts a PR review
  via GitHub MCP (`pull_request_review_write` with event COMMENT or REQUEST_CHANGES).

QA does **not** need the code only on GitHub to test — it tests locally, then reports on the PR.

## Security

- Never commit `.env`, credentials, or `.venv/`.
- Never print tokens in output.
- Use draft PRs when `githubDraftPr=true` in Context.

## GitLab

GitLab MCP is optional legacy. Prefer GitHub when `GITHUB_PERSONAL_ACCESS_TOKEN` is set.
"""


def _github_config_from_context(ctx: dict[str, Any]) -> dict[str, str]:
    owner = str(ctx.get("githubOwner") or os.getenv("GITHUB_OWNER", "")).strip()
    repo = str(ctx.get("githubRepo") or os.getenv("GITHUB_REPO", "")).strip()
    base = str(ctx.get("githubBaseBranch") or os.getenv("GITHUB_BASE_BRANCH", "main")).strip()
    return {"owner": owner, "repo": repo, "base": base}


def _load_mcp_tools(mcp_names: list[str]) -> tuple[list[Any], ExitStack]:
    stack: ExitStack = ExitStack()
    tools: list[Any] = []
    for name in mcp_names:
        client = MCP_FACTORIES[name]()
        stack.enter_context(client)
        tools.extend(client.list_tools_sync())
    return tools, stack


def _bedrock_model() -> BedrockModel:
    model_id = os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
    read_timeout = int(os.getenv("BEDROCK_READ_TIMEOUT", "600"))
    return BedrockModel(
        model_id=model_id,
        region_name=os.getenv("AWS_REGION", "us-east-2"),
        max_tokens=int(os.getenv("DEVOPS_AGENT_MAX_TOKENS", "8192")),
        streaming=True,
        boto_client_config=botocore.config.Config(
            read_timeout=read_timeout,
            connect_timeout=10,
            retries={"mode": "standard", "max_attempts": 2},
        ),
    )


@tool
def devops_list_publish_paths(target_app: str) -> str:
    """List repo-relative file paths that devops_git_publish will commit for this feature."""
    slug = slugify_feature(target_app)
    paths = collect_feature_artifact_paths(slug, root=_REPO_ROOT)
    if not paths:
        return f"No artifacts found for targetApp={slug}"
    lines = "\n".join(f"- {p}" for p in paths)
    return f"Publish paths for {slug} ({len(paths)} files):\n{lines}"


@tool
def devops_git_publish(
    target_app: str,
    branch: str = "",
    commit_message: str = "",
    push: bool = True,
) -> str:
    """Stage SDLC artifacts, commit on branch sdlc/<app>, optionally push to origin."""
    slug = slugify_feature(target_app)
    result = git_publish_feature(
        slug,
        branch=branch or default_branch_name(slug),
        commit_message=commit_message or f"feat({slug}): SDLC pipeline output",
        push=push,
        root=_REPO_ROOT,
    )
    return json.dumps(result, indent=2)


@tool
def devops_create_pull_request(
    target_app: str,
    owner: str,
    repo: str,
    head_branch: str,
    base_branch: str = "main",
    title: str = "",
    body: str = "",
    draft: bool = False,
) -> str:
    """Open a GitHub PR via gh CLI. Requires gh auth login or GH_TOKEN in env."""
    slug = slugify_feature(target_app)
    pr_title = title or f"feat({slug}): SDLC pipeline output"
    pr_body = body or f"Automated SDLC pipeline output for `{slug}`."
    result = gh_create_pull_request(
        owner=owner,
        repo=repo,
        title=pr_title,
        body=pr_body,
        head=head_branch,
        base=base_branch,
        draft=draft,
        root=_REPO_ROOT,
    )
    return json.dumps(result, indent=2)


def _github_mcp_enabled() -> bool:
    try:
        github_personal_access_token()
        return True
    except ValueError:
        return False


def _build_agent(*, include_github_mcp: bool = False) -> Agent:
    tools: list[Any] = [
        devops_list_publish_paths,
        devops_git_publish,
        devops_create_pull_request,
    ]
    if include_github_mcp:
        mcp_tools, stack = _load_mcp_tools(["github"])
        # Agent must be used inside stack context when MCP enabled — handled in run_task
        tools.extend(mcp_tools)
        _build_agent._mcp_stack = stack  # type: ignore[attr-defined]
    return Agent(
        agent_id=AGENT_NAME,
        name=AGENT_NAME,
        description="Publishes SDLC feature artifacts to GitHub and opens pull requests.",
        model=_bedrock_model(),
        system_prompt=DEVOPS_SYS_PROMPT,
        tools=tools,
    )


def _user_message(task: str, context: dict[str, Any] | None) -> str:
    if not context:
        return task
    return f"{task}\n\nContext:\n{json.dumps(context, indent=2)}"


def _enrich_devops_context(ctx: dict[str, Any]) -> None:
    app = slugify_feature(str(ctx["targetApp"]))
    gh = _github_config_from_context(ctx)
    if gh["owner"]:
        ctx.setdefault("githubOwner", gh["owner"])
    if gh["repo"]:
        ctx.setdefault("githubRepo", gh["repo"])
    ctx.setdefault("githubBaseBranch", gh["base"])
    ctx.setdefault("featureBranch", default_branch_name(app))
    ctx.setdefault("publishPaths", collect_feature_artifact_paths(app, root=_REPO_ROOT))

    handoff_candidates = (
        _REPO_ROOT / "agents" / "pipeline" / f"{app}.developer-handoff.json",
        _REPO_ROOT / "target-apps" / app / "DEVELOPER_HANDOFF.json",
    )
    for candidate in handoff_candidates:
        if candidate.is_file():
            ctx.setdefault("developerHandoffPath", candidate.relative_to(_REPO_ROOT).as_posix())
            break


def _write_devops_handoff(app: str, handoff: dict[str, Any]) -> str:
    path = _REPO_ROOT / "agents" / "pipeline" / f"{slugify_feature(app)}.devops-handoff.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    return path.relative_to(_REPO_ROOT).as_posix()


def _parse_handoff_json(summary: str) -> dict[str, Any]:
    match = __import__("re").search(r"```json\s*(\{.*?\})\s*```", summary, __import__("re").DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(1))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def run_task(
    task: str,
    context: dict[str, Any] | None = None,
    *,
    target_app: str | None = None,
) -> tuple[str, dict[str, Any]]:
    app = resolve_target_app(target_app, context, env_var="DEVOPS_TARGET_APP")
    ctx = context if context is not None else {"targetApp": app}
    ctx.setdefault("targetApp", app)
    enrich_handoff_context(ctx, include_db_paths=False)
    _enrich_devops_context(ctx)

    include_mcp = _github_mcp_enabled() and bool(_github_config_from_context(ctx)["owner"])
    if include_mcp:
        tools, stack = _load_mcp_tools(["github"])
        agent = Agent(
            agent_id=AGENT_NAME,
            name=AGENT_NAME,
            description="Publishes SDLC feature artifacts to GitHub.",
            model=_bedrock_model(),
            system_prompt=DEVOPS_SYS_PROMPT,
            tools=[
                devops_list_publish_paths,
                devops_git_publish,
                devops_create_pull_request,
                *tools,
            ],
        )
        with stack:
            summary = str(agent(_user_message(task, ctx)))
    else:
        agent = _build_agent(include_github_mcp=False)
        summary = str(agent(_user_message(task, ctx)))

    handoff = _parse_handoff_json(summary)
    if not handoff:
        handoff = {
            "targetApp": app,
            "status": "unknown",
            "featureBranch": ctx.get("featureBranch"),
            "githubOwner": ctx.get("githubOwner"),
            "githubRepo": ctx.get("githubRepo"),
        }
    handoff.setdefault("targetApp", app)
    handoff_path = _write_devops_handoff(app, handoff)
    summary += f"\n\n## DevOps handoff\nSaved: `{handoff_path}`\n"

    return summary, handoff


def serve_a2a(host: str = "127.0.0.1", port: int = A2A_PORT) -> None:
    skills = [
        AgentSkill(
            id="publish_feature",
            name="publish_feature",
            description="Publish SDLC feature artifacts to GitHub and open a pull request.",
            tags=["devops", "github", "git", "ci-cd"],
        )
    ]
    agent = _build_agent(include_github_mcp=_github_mcp_enabled())
    A2AServer(agent, host=host, port=port, skills=skills).serve()


def main() -> None:
    parser = argparse.ArgumentParser(description="DevOps agent — git publish + GitHub + A2A")
    parser.add_argument("--task", help="Task override (default: pipeline publish task)")
    parser.add_argument("--target-app", help="Feature slug under target-apps/")
    parser.add_argument(
        "--github-owner",
        help="GitHub org/user (overrides GITHUB_OWNER env)",
    )
    parser.add_argument(
        "--github-repo",
        help="GitHub repository name (overrides GITHUB_REPO env)",
    )
    parser.add_argument(
        "--github-base",
        default="",
        help="Base branch for PR (default: main or GITHUB_BASE_BRANCH)",
    )
    load_context_extra(parser)
    parser.add_argument("--serve-a2a", action="store_true")
    parser.add_argument("--port", type=int, default=A2A_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if args.serve_a2a:
        serve_a2a(host=args.host, port=args.port)
        return

    task = args.task or DEFAULT_PIPELINE_TASK
    try:
        ctx = resolve_cli_context(args)
    except TargetAppRequiredError as exc:
        parser.error(str(exc))

    if args.github_owner:
        ctx["githubOwner"] = args.github_owner
    if args.github_repo:
        ctx["githubRepo"] = args.github_repo
    if args.github_base:
        ctx["githubBaseBranch"] = args.github_base

    print(f"[{AGENT_NAME}] Publishing feature...")
    summary, _handoff = run_task(task, ctx, target_app=ctx.get("targetApp"))
    print("\n" + "=" * 60)
    print(summary)


if __name__ == "__main__":
    main()
