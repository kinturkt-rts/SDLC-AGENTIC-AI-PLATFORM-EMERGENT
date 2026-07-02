"""Smoke tests for gitlab-agent: MCP list, local S3 materialize+publish, or AgentCore invoke.

Examples:
  # MCP connectivity only
  python scripts/invoke-gitlab-agent-smoke.py --list-projects

  # Local: materialize S3 run + publish (same logic as AgentCore, no LLM)
  python scripts/invoke-gitlab-agent-smoke.py --local --app pr-diff-summarizer --run-id <uuid>

  # AgentCore runtime (LLM calls gitlab_publish_feature tool)
  python scripts/invoke-gitlab-agent-smoke.py --app pr-diff-summarizer --run-id <uuid>
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "agents"))

from _shared.agentcore_invoke import extract_text_from_a2a_jsonrpc, invoke_agent_runtime_a2a
from _shared.artifact_store import is_s3_store, list_run_artifact_keys, materialize_run
from _shared.env import load_repo_env
from _shared.gitlab_mcp_actions import (
    _collect_apps_repo_publish_files,
    _collect_monorepo_publish_files,
    collect_feature_artifact_entries,
    is_cloud_materialized_workspace,
    list_projects,
)


def _run_list_projects() -> int:
    result = list_projects(page=1, per_page=5)
    print(result)
    return 0 if result.get("ok") else 1


def _load_gitlab_agent_module():
    import importlib.util

    path = _REPO / "agents" / "gitlab-agent" / "gitlab_agent.py"
    spec = importlib.util.spec_from_file_location("gitlab_agent_module", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load gitlab agent from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_local_publish(app: str, run_id: str, *, apps_repo: bool) -> int:
    load_repo_env()
    if not is_s3_store():
        print("ARTIFACT_STORE is not s3; set ARTIFACT_STORE=s3 and ARTIFACT_S3_BUCKET in .env.local", file=sys.stderr)
        return 1

    keys = list_run_artifact_keys(run_id)
    print(f"S3 artifact keys for run {run_id}: {len(keys)}")
    if not keys:
        print("No artifacts in S3 for this runId.", file=sys.stderr)
        return 1

    root = materialize_run(run_id, Path(tempfile.mkdtemp(prefix="sdlc-gitlab-smoke-")))
    print(f"Materialized workspace: {root}")
    print(f"cloud_layout={is_cloud_materialized_workspace(root, app)}")
    entries = collect_feature_artifact_entries(app, root=root)
    print(f"mapped publish entries: {len(entries)}")

    files = (
        _collect_apps_repo_publish_files(app, root=root)
        if apps_repo
        else _collect_monorepo_publish_files(app, root=root)
    )
    print(f"publishable files: {len(files)}")
    if not files:
        print("File collection returned 0 files — redeploy gitlab_agent if cloud_layout=True but entries=0.", file=sys.stderr)
        return 1

    ga = _load_gitlab_agent_module()
    ctx = {"targetApp": app, "runId": run_id}
    print(f"Publishing {app} via GitLab MCP (local run_publish)...")
    summary, handoff = ga.run_publish(app, ctx, apps_repo=apps_repo, root=root)
    print(summary)
    return 0 if handoff.get("status") == "published" else 1


def _run_agentcore_publish(app: str, run_id: str, *, timeout: int) -> int:
    import json

    task = f"Publish SDLC artifacts for {app} to GitLab branch {app}."
    body = task + "\n\nContext:\n" + json.dumps({"targetApp": app, "runId": run_id}, indent=2)
    print("Invoking gitlab-agent on AgentCore...")
    print(body)
    print("---")
    result = invoke_agent_runtime_a2a("gitlab-agent", body, timeout=timeout)
    print("status:", result.get("status"))
    if result.get("error"):
        print("error:", result.get("error"))
    text = result.get("text") or extract_text_from_a2a_jsonrpc(result.get("response") or {})
    print("--- response ---")
    print(text[:8000])
    failed = "failed" in text.lower()[:400] or "## status\nfailed" in text
    return 0 if result.get("status") == "success" and not failed else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="GitLab agent smoke (MCP / local S3 / AgentCore)")
    parser.add_argument("--list-projects", action="store_true", help="MCP connectivity check only")
    parser.add_argument("--local", action="store_true", help="Materialize S3 + run_publish locally (no AgentCore)")
    parser.add_argument("--app", default="", help="Target app slug")
    parser.add_argument("--run-id", default="", help="Pipeline run UUID (required for publish modes)")
    parser.add_argument("--apps-repo", action="store_true", help="Publish to GITLAB_APPS_PROJECT_PATH layout")
    parser.add_argument("--timeout", type=int, default=900, help="AgentCore invoke timeout seconds")
    args = parser.parse_args()

    load_repo_env()

    if args.list_projects:
        sys.exit(_run_list_projects())

    if not args.app or not args.run_id:
        parser.error("--app and --run-id are required unless --list-projects")

    if args.local:
        sys.exit(_run_local_publish(args.app, args.run_id, apps_repo=args.apps_repo))

    sys.exit(_run_agentcore_publish(args.app, args.run_id, timeout=args.timeout))


if __name__ == "__main__":
    main()
