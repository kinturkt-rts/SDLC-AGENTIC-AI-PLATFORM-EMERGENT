"""GitHub agent — publishes SDLC artifacts via GitHub MCP after developer-agent.

Phase 1 MVP: deterministic push_files + create_pull_request to the showcase repo.
Each target app is published on its own branch (e.g. training-compliance) with a PR to main.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(_REPO_ROOT / "agents"))
from _shared.context_cli import load_context_extra, parse_context_args
from _shared.env import load_repo_env
from _shared.github_mcp_publish import github_repo_config, mcp_publish_feature
from _shared.github_publish import collect_feature_artifact_paths, github_feature_branch, slugify_feature
from _shared.pipeline_context import (
    TargetAppRequiredError,
    enrich_handoff_context,
    resolve_cli_context,
    resolve_target_app,
)

load_repo_env()
os.environ.setdefault("BYPASS_TOOL_CONSENT", "true")

from a2a.types import AgentSkill
from strands.multiagent.a2a import A2AServer

AGENT_NAME = "github-agent"
A2A_PORT = 9107

DEFAULT_PIPELINE_TASK = """\
Publish SDLC outputs for targetApp to the showcase GitHub repository.

Use github_publish_feature(targetApp) — pushes via GitHub MCP push_files and opens a PR.
Report status, branch, PR URL, and paths published.
"""


def _write_github_handoff(app: str, handoff: dict[str, Any]) -> str:
    path = _REPO_ROOT / "agents" / "pipeline" / f"{slugify_feature(app)}.github-handoff.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    return path.relative_to(_REPO_ROOT).as_posix()


def _enrich_github_context(ctx: dict[str, Any]) -> None:
    app = slugify_feature(str(ctx["targetApp"]))
    cfg = github_repo_config(
        owner=str(ctx.get("githubOwner") or ""),
        repo=str(ctx.get("githubRepo") or ""),
        base_branch=str(ctx.get("githubBaseBranch") or ""),
    )
    ctx.setdefault("githubOwner", cfg["owner"])
    ctx.setdefault("githubRepo", cfg["repo"])
    ctx.setdefault("githubBaseBranch", cfg["base"])
    ctx.setdefault("featureBranch", github_feature_branch(app))
    ctx.setdefault("publishPaths", collect_feature_artifact_paths(app, root=_REPO_ROOT))


def run_publish(
    target_app: str,
    context: dict[str, Any] | None = None,
    *,
    draft_pr: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Deterministic publish via GitHub MCP (no LLM)."""
    ctx = dict(context or {})
    app = resolve_target_app(target_app, ctx, env_var="GITHUB_TARGET_APP")
    ctx.setdefault("targetApp", app)
    enrich_handoff_context(ctx, include_db_paths=False)
    _enrich_github_context(ctx)

    result = mcp_publish_feature(
        app,
        owner=str(ctx.get("githubOwner", "")),
        repo=str(ctx.get("githubRepo", "")),
        base_branch=str(ctx.get("githubBaseBranch", "")),
        draft_pr=draft_pr or bool(ctx.get("githubDraftPr")),
        root=_REPO_ROOT,
    )

    handoff = {
        "targetApp": app,
        "status": result.get("status", "failed" if not result.get("ok") else "published"),
        "branch": result.get("branch"),
        "githubOwner": result.get("githubOwner"),
        "githubRepo": result.get("githubRepo"),
        "githubBaseBranch": result.get("githubBaseBranch"),
        "pathsPublished": result.get("pathsPublished", []),
        "pullRequestUrl": result.get("pullRequestUrl"),
        "pullRequestNumber": result.get("pullRequestNumber"),
        "repoUrl": result.get("repoUrl"),
        "branchUrl": result.get("branchUrl"),
        "error": result.get("error"),
    }
    handoff_path = _write_github_handoff(app, handoff)

    if not result.get("ok"):
        summary = (
            f"## status\nfailed\n\n"
            f"## error\n{result.get('error', 'unknown')}\n\n"
            f"## handoff\nSaved: `{handoff_path}`"
        )
        return summary, handoff

    summary = (
        f"## status\npublished\n\n"
        f"## branch\n`{result.get('branch')}`\n\n"
        f"## pull_request\n{result.get('pullRequestUrl')}\n\n"
        f"## paths_published\n"
        + "\n".join(f"- `{p}`" for p in result.get("pathsPublished", []))
        + f"\n\n## handoff\nSaved: `{handoff_path}`\n"
    )
    return summary, handoff


def serve_a2a(host: str = "127.0.0.1", port: int = A2A_PORT) -> None:
    """Minimal A2A card — publish is invoked via CLI in Phase 1."""
    from strands import Agent
    from strands.models import BedrockModel

    agent = Agent(
        agent_id=AGENT_NAME,
        name=AGENT_NAME,
        description="Publishes SDLC feature artifacts to GitHub via MCP.",
        model=BedrockModel(
            model_id=os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
            region_name=os.getenv("AWS_REGION", "us-east-2"),
        ),
        system_prompt="You publish SDLC apps to GitHub. Direct users to github_publish_feature CLI.",
        tools=[],
    )
    skills = [
        AgentSkill(
            id="publish_feature",
            name="publish_feature",
            description="Publish SDLC artifacts to GitHub showcase repo via MCP.",
            tags=["github", "publish", "mcp"],
        )
    ]
    A2AServer(agent, host=host, port=port, skills=skills).serve()


def main() -> None:
    parser = argparse.ArgumentParser(description="GitHub agent — MCP publish to showcase repo")
    parser.add_argument("--target-app", help="Feature slug under target-apps/")
    parser.add_argument("--github-owner", help="GitHub org/user (default: GITHUB_OWNER or kinturkt-rts)")
    parser.add_argument("--github-repo", help="Repository name (default: GITHUB_REPO or SDLC-Agentic-AI-Platform)")
    parser.add_argument("--github-base", default="", help="PR base branch (default: main)")
    parser.add_argument("--draft-pr", action="store_true", help="Open PR as draft")
    load_context_extra(parser)
    parser.add_argument("--serve-a2a", action="store_true")
    parser.add_argument("--port", type=int, default=A2A_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if args.serve_a2a:
        serve_a2a(host=args.host, port=args.port)
        return

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

    app = resolve_target_app(args.target_app, ctx, env_var="GITHUB_TARGET_APP")
    print(f"[{AGENT_NAME}] Publishing {app} via GitHub MCP...")
    summary, handoff = run_publish(app, ctx, draft_pr=args.draft_pr)
    print("\n" + "=" * 60)
    print(summary)
    if not handoff.get("pullRequestUrl") and handoff.get("status") != "published":
        sys.exit(1)


if __name__ == "__main__":
    main()
