"""GitLab agent — publishes SDLC artifacts via  MCP after developer-agent.

Deterministic gitlab_commit_create via gitlab-mcp-server.
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
from _shared.gitlab_mcp_actions import (
    collect_feature_artifact_paths,
    create_mr_note,
    gitlab_apps_project_path,
    gitlab_base_branch,
    gitlab_repo_config,
    list_branch_files,
    list_mr_notes,
    list_projects,
    publish_feature,
    slugify_feature,
)
from _shared.pipeline_context import (
    TargetAppRequiredError,
    enrich_handoff_context,
    resolve_cli_context,
    resolve_target_app,
)

load_repo_env()
os.environ.setdefault("BYPASS_TOOL_CONSENT", "true")

AGENT_NAME = "gitlab-agent"

def _write_gitlab_handoff(app: str, handoff: dict[str, Any]) -> str:
    path = _REPO_ROOT / "agents" / "pipeline" / f"{slugify_feature(app)}.gitlab-handoff.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    return path.relative_to(_REPO_ROOT).as_posix()


def _enrich_gitlab_context(
    ctx: dict[str, Any],
    *,
    layout: str = "monorepo",
    root: Path | None = None,
) -> None:
    publish_root = root or _REPO_ROOT
    app = slugify_feature(str(ctx["targetApp"]))
    if layout == "apps":
        ctx.setdefault("gitlabProject", gitlab_apps_project_path())
    else:
        cfg = gitlab_repo_config(
            project=str(ctx.get("gitlabProject") or ""),
            base_branch=str(ctx.get("gitlabBaseBranch") or ""),
        )
        ctx.setdefault("gitlabProject", cfg["project"])
    ctx.setdefault("gitlabBaseBranch", gitlab_base_branch())
    ctx.setdefault("publishPaths", collect_feature_artifact_paths(app, root=publish_root))


def run_publish(
    target_app: str,
    context: dict[str, Any] | None = None,
    *,
    draft_mr: bool = False,
    open_mr: bool = False,
    branch: str | None = None,
    apps_repo: bool = False,
    root: Path | None = None,
) -> tuple[str, dict[str, Any]]:
    """Deterministic publish via jmrplens GitLab MCP (no LLM)."""
    ctx = dict(context or {})
    publish_root = root or _REPO_ROOT
    app = resolve_target_app(target_app, ctx, env_var="GITLAB_TARGET_APP")
    ctx.setdefault("targetApp", app)
    enrich_handoff_context(ctx, include_db_paths=False)

    layout = "apps" if apps_repo or ctx.get("gitlabPublishLayout") == "apps" else "monorepo"
    _enrich_gitlab_context(ctx, layout=layout, root=publish_root)

    result = publish_feature(
        app,
        project=str(ctx.get("gitlabProject", "")),
        base_branch=str(ctx.get("gitlabBaseBranch", "")),
        branch=branch or (str(ctx["featureBranch"]) if ctx.get("featureBranch") else None),
        draft_mr=draft_mr or bool(ctx.get("gitlabDraftMr")),
        open_mr=open_mr or bool(ctx.get("gitlabOpenMr")),
        root=publish_root,
        layout=layout,
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


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="GitLab agent — MCP publish to platform repo")
    parser.add_argument("--target-app", help="Feature slug under target-apps/")
    parser.add_argument(
        "--gitlab-project",
        help="GitLab project path or numeric id (default: GITLAB_PROJECT_PATH)",
    )
    parser.add_argument("--gitlab-base", default="", help="Branch to fork from (default: main)")
    parser.add_argument("--branch", default="", help="Override publish branch (default: sdlc/<app> or <app> with --apps-repo)")
    parser.add_argument(
        "--apps-repo",
        action="store_true",
        help="Publish to GITLAB_APPS_PROJECT_PATH with app files at branch root (branch default: <app>)",
    )
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
    args = parser.parse_args()

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
        apps_repo=args.apps_repo,
    )
    print("\n" + "=" * 60)
    print(summary)
    if not handoff.get("mergeRequestUrl") and handoff.get("status") != "published":
        sys.exit(1)


if __name__ == "__main__":
    main()
