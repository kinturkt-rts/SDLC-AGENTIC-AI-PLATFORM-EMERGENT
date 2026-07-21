"""GitLab agent — publishes SDLC artifacts to a per-app branch via GitLab MCP."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(_REPO_ROOT / "agents"))
from _shared.context_cli import load_context_extra, parse_context_args
from _shared.env import load_repo_env
from _shared.artifact_store import resolve_run_id
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
    write_pipeline_run_marker,
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

    # Embed runId in the published app tree so GitLab CI can set PIPELINE_RUN_ID
    # and devops-agent can write the live URL back to the same S3 run handoff.
    run_id = resolve_run_id(ctx)
    marker_rel = write_pipeline_run_marker(app, run_id or "", root=publish_root)
    if run_id:
        ctx["runId"] = run_id
    # Refresh publish path list after marker write (used in handoff context only).
    ctx["publishPaths"] = collect_feature_artifact_paths(app, root=publish_root)

    publish_started = time.monotonic()
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
    publish_elapsed = round(time.monotonic() - publish_started, 2)

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
        "elapsedSec": result.get("elapsedSec", publish_elapsed),
        "commitCount": result.get("commitCount"),
        "fileCount": result.get("fileCount"),
        "mcpUrl": result.get("mcpUrl"),
        "runId": run_id,
        "pipelineRunMarker": marker_rel,
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
        f"## elapsed_sec\n{handoff.get('elapsedSec')}\n\n"
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


def _prompt_to_text(message: Any) -> str:
    if isinstance(message, str):
        return message
    if isinstance(message, list):
        parts: list[str] = []
        for item in message:
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(message)


def parse_publish_request(message: Any) -> tuple[str, str, dict[str, Any]] | None:
    """Parse targetApp and runId from an A2A/AgentCore publish message."""
    import re

    text = _prompt_to_text(message)
    ctx: dict[str, Any] = {}
    if "Context:" in text:
        _, _, json_part = text.partition("Context:")
        try:
            parsed = json.loads(json_part.strip())
            if isinstance(parsed, dict):
                ctx = parsed
        except json.JSONDecodeError:
            pass

    target = str(
        ctx.get("targetApp") or ctx.get("target_app") or ctx.get("target-app") or ""
    ).strip()
    run_id = str(ctx.get("runId") or ctx.get("run_id") or ctx.get("run-id") or "").strip()

    if not target:
        match = re.search(r"target_app\s*=\s*['\"]([^'\"]+)['\"]", text, re.I)
        if match:
            target = match.group(1).strip()
    if not target:
        match = re.search(r"for\s+([\w-]+)\s+to\s+GitLab", text, re.I)
        if match:
            target = match.group(1).strip()

    if not run_id:
        match = re.search(r"run_id\s*=\s*['\"]([^'\"]+)['\"]", text, re.I)
        if match:
            run_id = match.group(1).strip()

    if not target:
        return None
    return target, run_id, ctx


def _apps_repo_enabled(ctx: dict[str, Any] | None = None) -> bool:
    if ctx and str(ctx.get("gitlabPublishLayout") or "").strip().lower() == "apps":
        return True
    return os.getenv("GITLAB_APPS_REPO", "").strip().lower() in {"1", "true", "yes", "on"}


def run_publish_for_agentcore(
    target_app: str,
    run_id: str = "",
    context: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Materialize S3 run artifacts (when configured) and publish via MCP — no LLM."""
    import logging
    import tempfile

    from _shared.artifact_store import (
        DEV_READY_FAILED,
        DEV_READY_MISSING,
        DEV_READY_PARTIAL,
        classify_developer_readiness,
        is_s3_store,
        list_run_artifact_keys,
        materialize_run,
        put_handoff,
    )
    from _shared.pipeline_context import slugify_feature

    logger = logging.getLogger(__name__)

    ctx = dict(context or {})
    rid = (
        run_id.strip()
        or str(ctx.get("runId") or ctx.get("run_id") or "").strip()
        or os.getenv("PIPELINE_RUN_ID", "").strip()
    )
    if rid:
        ctx["runId"] = rid

    root: Path | None = None
    if rid and is_s3_store():
        slug = slugify_feature(target_app)
        wait_sec = float(os.getenv("SDLC_GITLAB_PRE_PUBLISH_WAIT_SEC", "30"))
        decision, dev_handoff = classify_developer_readiness(rid, slug, timeout_sec=wait_sec)
        if decision in {DEV_READY_FAILED, DEV_READY_MISSING}:
            if decision == DEV_READY_FAILED:
                reason = str((dev_handoff or {}).get("error") or "developer-agent reported failure")
                error = f"GitLab publish blocked: developer-agent failed: {reason}"
            else:
                error = (
                    "GitLab publish blocked: developer-agent produced no publishable "
                    f"app artifacts for run {rid}"
                )
            logger.error("%s", error)
            handoff = {
                "targetApp": slug,
                "status": "failed",
                "error": error,
                "pathsPublished": [],
            }
            put_handoff(rid, "gitlab", handoff)
            return f"## status\nfailed\n\n## error\n{error}\n", handoff
        if decision == DEV_READY_PARTIAL:
            logger.warning(
                "developer handoff not finalized for run %s (status=%s); "
                "publishing delivered artifacts best-effort",
                rid,
                (dev_handoff or {}).get("status", "in_progress"),
            )
        keys = list_run_artifact_keys(rid)
        root = materialize_run(rid, Path(tempfile.mkdtemp(prefix="sdlc-gitlab-")))
        if not keys:
            handoff = {
                "targetApp": slugify_feature(target_app),
                "status": "failed",
                "error": f"No S3 artifacts for runId {rid}",
                "pathsPublished": [],
            }
            put_handoff(rid, "gitlab", handoff)
            return f"## status\nfailed\n\n## error\nNo S3 artifacts for runId {rid}\n", handoff

    summary, handoff = run_publish(
        target_app,
        ctx,
        open_mr=os.getenv("GITLAB_OPEN_MR", "").strip().lower() in {"1", "true", "yes", "on"},
        apps_repo=_apps_repo_enabled(ctx),
        root=root,
    )
    if rid and is_s3_store():
        put_handoff(rid, "gitlab", handoff)
    return summary, handoff


def execute_publish_message(message: Any) -> str:
    """Deterministic AgentCore handler: parse message → publish → return summary text."""
    text = _prompt_to_text(message)
    from _shared.control_plane_health import is_control_plane_health_check

    if is_control_plane_health_check(text):
        return "OK"
    parsed = parse_publish_request(message)
    if parsed is None:
        example = {
            "targetApp": "pr-diff-summarizer",
            "runId": "92099e5f-be02-4894-9276-67f2e5a72343",
        }
        return (
            "GitLab publish could not start — no targetApp found in the message.\n\n"
            "Send a message like:\n"
            f"Publish SDLC artifacts for pr-diff-summarizer to GitLab.\n\n"
            f"Context:\n{json.dumps(example, indent=2)}"
        )

    target_app, run_id, ctx = parsed
    summary, handoff = run_publish_for_agentcore(target_app, run_id, ctx)
    if handoff.get("status") != "published":
        return summary
    return summary


def _agent_result_from_text(text: str) -> Any:
    from strands.agent.agent_result import AgentResult
    from strands.telemetry.metrics import EventLoopMetrics

    return AgentResult(
        stop_reason="end_turn",
        message={"role": "assistant", "content": [{"text": text}]},
        metrics=EventLoopMetrics(),
        state={},
    )


def build_gitlab_pipeline_agent() -> Any:
    """AgentCore mode: publish directly on each A2A message (no LLM round-trip)."""
    from collections.abc import AsyncIterator

    from _shared.runner import build_agent
    from strands.types._events import AgentResultEvent

    agent = build_agent("gitlab-agent", system_prompt="Deterministic GitLab publish.", enable_a2a_peers=False)

    def publish_invoke(message: Any, **kwargs: Any) -> str:
        del kwargs
        return execute_publish_message(message)

    async def publish_stream_async(
        prompt: Any = None,
        *,
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        del invocation_state, kwargs
        summary = execute_publish_message(prompt)
        yield AgentResultEvent(result=_agent_result_from_text(summary)).as_dict()

    agent.__call__ = publish_invoke  # type: ignore[method-assign]
    agent.stream_async = publish_stream_async  # type: ignore[method-assign]
    return agent


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
