"""GitLab agent — publishes SDLC artifacts via jmrplens MCP after developer-agent.

Deterministic gitlab_commit_create via jmrplens/gitlab-mcp-server (same binary as Cursor).
Each target app uses branch sdlc/<app>; republishs update files on that branch.
MR to main is opt-in (--open-mr).
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
from _shared.github_publish import collect_feature_artifact_paths, slugify_feature
from _shared.gitlab_mcp_ops import (
    create_mr_note,
    list_branch_files,
    list_mr_notes,
    list_projects,
)
from _shared.gitlab_mcp_publish import gitlab_repo_config, publish_feature
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

AGENT_NAME = "gitlab-agent"
A2A_PORT = 9110

DEFAULT_PIPELINE_TASK = """\
Publish SDLC outputs for targetApp to the platform GitLab repository.

Use gitlab_publish_feature(targetApp) — pushes to branch sdlc/<app> (reused per app).
Republishs update existing files on that branch; a different targetApp uses its own branch.
Merge requests to main are opt-in (--open-mr); default is branch-only publish.
Report status, branch URL, paths published, and optional MR URL.
"""


def _write_gitlab_handoff(app: str, handoff: dict[str, Any]) -> str:
    path = _REPO_ROOT / "agents" / "pipeline" / f"{slugify_feature(app)}.gitlab-handoff.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    return path.relative_to(_REPO_ROOT).as_posix()


def _enrich_gitlab_context(ctx: dict[str, Any]) -> None:
    app = slugify_feature(str(ctx["targetApp"]))
    cfg = gitlab_repo_config(
        project=str(ctx.get("gitlabProject") or ""),
        base_branch=str(ctx.get("gitlabBaseBranch") or ""),
    )
    ctx.setdefault("gitlabProject", cfg["project"])
    ctx.setdefault("gitlabBaseBranch", cfg["base"])
    ctx.setdefault("publishPaths", collect_feature_artifact_paths(app, root=_REPO_ROOT))


def run_publish(
    target_app: str,
    context: dict[str, Any] | None = None,
    *,
    draft_mr: bool = False,
    open_mr: bool = False,
    branch: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Deterministic publish via jmrplens GitLab MCP (no LLM)."""
    ctx = dict(context or {})
    app = resolve_target_app(target_app, ctx, env_var="GITLAB_TARGET_APP")
    ctx.setdefault("targetApp", app)
    enrich_handoff_context(ctx, include_db_paths=False)
    _enrich_gitlab_context(ctx)

    result = publish_feature(
        app,
        project=str(ctx.get("gitlabProject", "")),
        base_branch=str(ctx.get("gitlabBaseBranch", "")),
        branch=branch or (str(ctx["featureBranch"]) if ctx.get("featureBranch") else None),
        draft_mr=draft_mr or bool(ctx.get("gitlabDraftMr")),
        open_mr=open_mr or bool(ctx.get("gitlabOpenMr")),
        root=_REPO_ROOT,
    )

    handoff = {
        "targetApp": app,
        "status": result.get("status", "failed" if not result.get("ok") else "published"),
        "branch": result.get("branch"),
        "gitlabProject": result.get("gitlabProject"),
        "gitlabBaseBranch": result.get("gitlabBaseBranch"),
        "openMergeRequest": result.get("openMergeRequest", False),
        "pathsPublished": result.get("pathsPublished", []),
        "mergeRequestUrl": result.get("mergeRequestUrl"),
        "mergeRequestIid": result.get("mergeRequestIid"),
        "repoUrl": result.get("repoUrl"),
        "branchUrl": result.get("branchUrl"),
        "error": result.get("error"),
    }
    handoff_path = _write_gitlab_handoff(app, handoff)

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
        f"## branch_url\n{result.get('branchUrl')}\n\n"
    )
    if result.get("mergeRequestUrl"):
        summary += f"## merge_request\n{result.get('mergeRequestUrl')}\n\n"
    else:
        summary += "## merge_request\n(not opened — branch-only publish)\n\n"
    summary += (
        "## paths_published\n"
        + "\n".join(f"- `{p}`" for p in result.get("pathsPublished", []))
        + f"\n\n## handoff\nSaved: `{handoff_path}`\n"
    )
    return summary, handoff


def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2))


def run_list_projects(*, page: int = 1, per_page: int = 20) -> int:
    result = list_projects(page=page, per_page=per_page)
    _print_json(result)
    return 0 if result.get("ok") else 1


def run_list_branch_files(*, branch: str, project: str | None = None) -> int:
    result = list_branch_files(branch=branch, project_id=project, blobs_only=True)
    _print_json(result)
    return 0 if result.get("ok") else 1


def run_list_mr_notes(*, mr_iid: int, project: str | None = None) -> int:
    result = list_mr_notes(mr_iid=mr_iid, project_id=project)
    _print_json(result)
    return 0 if result.get("ok") else 1


def run_mr_comment(*, mr_iid: int, body: str, project: str | None = None) -> int:
    result = create_mr_note(mr_iid=mr_iid, body=body, project_id=project)
    _print_json(result)
    return 0 if result.get("ok") else 1


def serve_a2a(host: str = "127.0.0.1", port: int = A2A_PORT) -> None:
    from strands import Agent
    from strands.models import BedrockModel

    agent = Agent(
        agent_id=AGENT_NAME,
        name=AGENT_NAME,
        description="Publishes SDLC feature artifacts to GitLab via MCP.",
        model=BedrockModel(
            model_id=os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
            region_name=os.getenv("AWS_REGION", "us-east-2"),
        ),
        system_prompt="You publish SDLC apps to GitLab. Direct users to gitlab-agent CLI.",
        tools=[],
    )
    skills = [
        AgentSkill(
            id="publish_feature",
            name="publish_feature",
            description="Publish SDLC artifacts to GitLab via self-hosted MCP.",
            tags=["gitlab", "publish", "mcp"],
        )
    ]
    A2AServer(agent, host=host, port=port, skills=skills).serve()


def main() -> None:
    parser = argparse.ArgumentParser(description="GitLab agent — MCP publish to platform repo")
    parser.add_argument("--target-app", help="Feature slug under target-apps/")
    parser.add_argument(
        "--gitlab-project",
        help="GitLab project path or numeric id (default: GITLAB_PROJECT_PATH)",
    )
    parser.add_argument("--gitlab-base", default="", help="Branch to fork from (default: main)")
    parser.add_argument("--branch", default="", help="Override publish branch (default: sdlc/<app>)")
    parser.add_argument("--open-mr", action="store_true", help="Open merge request to --gitlab-base / main")
    parser.add_argument("--draft-mr", action="store_true", help="Open MR as draft (requires --open-mr)")
    parser.add_argument(
        "--list-projects",
        action="store_true",
        help="List GitLab projects (MCP gitlab_project_list)",
    )
    parser.add_argument(
        "--list-branch-files",
        metavar="BRANCH",
        help="List files on a branch (MCP gitlab_repository_tree)",
    )
    parser.add_argument(
        "--list-mr-notes",
        type=int,
        metavar="MR_IID",
        help="List comments on a merge request (MCP gitlab_mr_notes_list)",
    )
    parser.add_argument(
        "--mr-comment",
        type=int,
        metavar="MR_IID",
        help="Post a comment on a merge request (MCP gitlab_mr_note_create)",
    )
    parser.add_argument("--comment-body", default="", help="MR comment markdown (with --mr-comment)")
    parser.add_argument("--comment-body-file", default="", help="Read MR comment body from file")
    parser.add_argument("--page", type=int, default=1, help="Page for --list-projects")
    parser.add_argument("--per-page", type=int, default=20, help="Page size for --list-projects")
    load_context_extra(parser)
    parser.add_argument(
        "--no-auto-context",
        action="store_true",
        help="Skip auto-load of agents/pipeline/<app>.context.json",
    )
    parser.add_argument("--serve-a2a", action="store_true")
    parser.add_argument("--port", type=int, default=A2A_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if args.serve_a2a:
        serve_a2a(host=args.host, port=args.port)
        return

    project_override = args.gitlab_project or None

    if args.list_projects:
        sys.exit(run_list_projects(page=args.page, per_page=args.per_page))

    if args.list_branch_files:
        sys.exit(run_list_branch_files(branch=args.list_branch_files, project=project_override))

    if args.list_mr_notes is not None:
        sys.exit(run_list_mr_notes(mr_iid=args.list_mr_notes, project=project_override))

    if args.mr_comment is not None:
        body = args.comment_body.strip()
        if args.comment_body_file:
            body = Path(args.comment_body_file).read_text(encoding="utf-8").strip()
        if not body:
            parser.error("--mr-comment requires --comment-body or --comment-body-file")
        sys.exit(run_mr_comment(mr_iid=args.mr_comment, body=body, project=project_override))

    try:
        ctx, app = resolve_cli_context(
            args.target_app,
            parse_context_args(args),
            no_auto_context=args.no_auto_context,
            env_var="GITLAB_TARGET_APP",
        )
    except TargetAppRequiredError as exc:
        parser.error(str(exc))

    if args.gitlab_project:
        ctx["gitlabProject"] = args.gitlab_project
    if args.gitlab_base:
        ctx["gitlabBaseBranch"] = args.gitlab_base
    if args.branch:
        ctx["featureBranch"] = args.branch

    print(f"[{AGENT_NAME}] Publishing {app} via GitLab MCP...")
    summary, handoff = run_publish(
        app,
        ctx,
        draft_mr=args.draft_mr,
        open_mr=args.open_mr,
        branch=args.branch or None,
    )
    print("\n" + "=" * 60)
    print(summary)
    if not handoff.get("mergeRequestUrl") and handoff.get("status") != "published":
        sys.exit(1)


if __name__ == "__main__":
    main()
