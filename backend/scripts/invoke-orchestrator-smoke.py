"""Smoke invoke for orchestrator-agent AgentCore runtime (deterministic pipeline).

Default: full cloud chain (product → architect → database → RDS apply in orchestrator
→ developer → gitlab). Brief is uploaded to S3 from this machine; all agent work runs
on AgentCore.

The Next.js dashboard (ARTIFACT_STORE=s3) invokes orchestrator via AgentCore SDK
directly — no local Python subprocess. This script remains for CLI/manual use.

DB + RDS only (skips developer/gitlab):
  python scripts/invoke-orchestrator-smoke.py --app inventory-app --run-id smoke-2 --full

Local RDS fallback (dev only — use when orchestrator cannot reach public RDS):
  python scripts/invoke-orchestrator-smoke.py --app inventory-app --run-id smoke-2 --skip-postgres --apply-rds-local

Connectivity check only (skip all agent steps):
  python scripts/invoke-orchestrator-smoke.py --app inventory-app --run-id smoke-2 --skip-product --skip-architect --skip-db --skip-developer
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "agents"))

from _shared.agentcore_invoke import extract_text_from_a2a_jsonrpc, invoke_agent_runtime_a2a

_RUNTIMES_JSON = _REPO / "config" / "agentcore" / "runtimes.json"


def _resolve_artifact_bucket() -> str:
    """ARTIFACT_S3_BUCKET from env (.env.local) or config/agentcore/runtimes.json."""
    import os

    from _shared.env import load_repo_env

    load_repo_env()
    bucket = os.getenv("ARTIFACT_S3_BUCKET", "").strip()
    if bucket:
        return bucket
    if _RUNTIMES_JSON.is_file():
        data = json.loads(_RUNTIMES_JSON.read_text(encoding="utf-8"))
        bucket = str((data.get("artifactStore") or {}).get("ARTIFACT_S3_BUCKET") or "").strip()
        if bucket:
            os.environ.setdefault("ARTIFACT_STORE", "s3")
            os.environ["ARTIFACT_S3_BUCKET"] = bucket
            return bucket
    raise SystemExit(
        "ARTIFACT_S3_BUCKET is not set.\n"
        "Add ARTIFACT_S3_BUCKET=sdlc-agentic-ai-app-artifacts to .env.local, or export:\n"
        '  $env:ARTIFACT_S3_BUCKET = "sdlc-agentic-ai-app-artifacts"'
    )


def _upload_input_brief(app: str, run_id: str) -> str:
    """Upload inputs/<app>.txt to S3 under the run prefix. Returns the S3 key."""
    import boto3
    import os

    bucket = _resolve_artifact_bucket()
    local = _REPO / "inputs" / f"{app}.txt"
    if not local.is_file():
        raise FileNotFoundError(f"No input file at {local}")
    key = f"runs/{run_id}/inputs/{app}.txt"
    boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-2")).upload_file(
        str(local), bucket, key
    )
    print(f"Uploaded s3://{bucket}/{key}")
    return f"inputs/{app}.txt"


def _apply_rds_local(app: str, run_id: str) -> int:
    """Pull SQL from S3 and apply to RDS from this machine (smoke-test fallback when skip_postgres=True)."""
    from _shared.artifact_store import materialize_run, run_sql_artifact_keys
    from _shared.env import load_repo_env
    from _shared.pipeline_context import target_app_root_rel

    load_repo_env()
    keys = run_sql_artifact_keys(run_id, app)
    if not keys:
        print(
            f"[apply-rds-local] No SQL artifacts in S3 for run {run_id} / {app}",
            file=sys.stderr,
        )
        return 1

    workspace = materialize_run(run_id)
    app_root = target_app_root_rel(app)
    sql_dir = workspace / app_root.replace("/", "\\") / "db" / "sql"
    if not sql_dir.is_dir():
        legacy = workspace / "target-apps" / app / "db" / "sql"
        sql_dir = legacy if legacy.is_dir() else sql_dir
    if not sql_dir.is_dir() or not any(sql_dir.glob("*.sql")):
        print(f"[apply-rds-local] Materialized workspace missing sql dir: {sql_dir}", file=sys.stderr)
        return 1

    print(f"[apply-rds-local] Applying {len(list(sql_dir.glob('*.sql')))} file(s) from {sql_dir}")
    proc = subprocess.run(
        [
            sys.executable,
            str(_REPO / "scripts" / "apply_sql_to_rds.py"),
            "--sql-dir",
            str(sql_dir),
            "--target-app",
            app,
            "--verbose",
            "--reset-schema",
        ],
        cwd=_REPO,
    )
    return int(proc.returncode)


def _update_run_json(
    run_id: str,
    *,
    status: str | None = None,
    current_step: str | None = None,
    error: str | None = None,
) -> None:
    """Update agents/pipeline/runs/<runId>/run.json so the UI reflects real progress."""
    path = _REPO / "agents" / "pipeline" / "runs" / run_id / "run.json"
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if status:
            data["status"] = status
            if status in ("completed", "failed", "cancelled"):
                data["finishedAt"] = datetime.now(timezone.utc).isoformat()
        if current_step:
            data["currentStep"] = current_step
            for step in data.get("steps", []):
                if step["name"] == current_step:
                    step["status"] = "running"
                elif step.get("status") == "running":
                    step["status"] = "completed"
        if error:
            data["error"] = error
        elif status == "completed":
            data["error"] = None
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass


def _get_handoff_safe(run_id: str) -> dict[str, Any] | None:
    from _shared.artifact_store import get_handoff

    return get_handoff(run_id, "gitlab")


def _gitlab_handoff_exists(run_id: str, app: str) -> bool:
    """Check if gitlab handoff exists in S3 (canonical or slug-prefixed layout)."""
    from _shared.artifact_store import get_handoff

    return get_handoff(run_id, "gitlab") is not None


def _gitlab_handoff_status(run_id: str) -> str | None:
    """Return 'published', 'failed', or None if no handoff."""
    from _shared.artifact_store import get_handoff

    handoff = get_handoff(run_id, "gitlab")
    if not handoff:
        return None
    return str(handoff.get("status") or "").strip().lower() or None


def _reconcile_run_steps(run_id: str, app: str, skip_gitlab: bool) -> None:
    """Update run.json step statuses based on S3 artifacts (cloud runs don't update step-by-step)."""
    from _shared.artifact_store import get_handoff, list_run_artifact_keys

    path = _REPO / "agents" / "pipeline" / "runs" / run_id / "run.json"
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return

    keys = set(list_run_artifact_keys(run_id))
    keys_lower = {k.lower() for k in keys}
    slug = app

    def has(pattern: str) -> bool:
        return any(pattern in k for k in keys_lower)

    # Detect which agent artifacts exist in S3
    has_prd = has(f"{slug}/docs/prd/") or has("docs/prd/")
    has_design = has(f"{slug}/docs/design/") or has("docs/design/")
    has_diagram = has(f"{slug}/docs/diagrams/") or has("docs/diagrams/")
    has_sql = has(f"{slug}/db/sql/") or has("db/sql/")
    has_code = has(f"{slug}/app/") or has(f"{slug}/main.py")
    gitlab_status = _gitlab_handoff_status(run_id)

    for step in data.get("steps", []):
        name = step["name"]
        if name == "product-agent":
            if has_prd:
                step["status"] = "completed"
        elif name == "architect-agent":
            if has_design or has_diagram:
                step["status"] = "completed"
        elif name == "database-agent":
            if has_sql:
                step["status"] = "completed"
        elif name == "developer-agent":
            if has_code:
                step["status"] = "completed"
        elif name == "gitlab-agent":
            if gitlab_status == "published":
                step["status"] = "completed"
            elif gitlab_status == "failed":
                step["status"] = "failed"
            elif not skip_gitlab and has_code:
                step["status"] = "running"
        elif name == "qa-agent":
            step["status"] = "skipped"

    data["error"] = None
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _run_gitlab_fallback_cloud(app: str, run_id: str, timeout: int) -> int:
    """Invoke gitlab-agent on AgentCore as fallback (publishes whatever is in S3)."""
    task = f"Publish SDLC artifacts for {app} to GitLab branch sdlc/{app}."
    body = task + "\n\nContext:\n" + json.dumps({"targetApp": app, "runId": run_id}, indent=2)
    print(f"[gitlab-fallback] Invoking gitlab-agent on AgentCore (timeout={timeout}s)...")
    result = invoke_agent_runtime_a2a("gitlab-agent", body, timeout=timeout)
    status = result.get("status")
    print(f"[gitlab-fallback] cloud status: {status}")
    if result.get("error"):
        print(f"[gitlab-fallback] cloud error: {result.get('error')}")
    text = result.get("text") or ""
    if not text and result.get("response"):
        text = extract_text_from_a2a_jsonrpc(result["response"])
    if text:
        print(f"[gitlab-fallback] cloud response: {text[:1500]}")
    return 0 if status == "success" else 1


def _run_gitlab_fallback_local(app: str, run_id: str) -> int:
    """Materialize S3 run artifacts + run_publish locally (no AgentCore, no LLM)."""
    import importlib.util
    import tempfile

    from _shared.artifact_store import (
        is_s3_store,
        list_run_artifact_keys,
        materialize_run,
    )

    if not is_s3_store():
        print("[gitlab-fallback-local] ARTIFACT_STORE is not s3", file=sys.stderr)
        return 1

    keys = list_run_artifact_keys(run_id)
    if not keys:
        print(f"[gitlab-fallback-local] No S3 artifacts for run {run_id}", file=sys.stderr)
        return 1

    root = materialize_run(run_id, Path(tempfile.mkdtemp(prefix="sdlc-gitlab-fb-")))
    print(f"[gitlab-fallback-local] Materialized {len(keys)} artifacts at {root}")

    spec = importlib.util.spec_from_file_location(
        "gitlab_agent_fb", _REPO / "agents" / "gitlab-agent" / "gitlab_agent.py"
    )
    if spec is None or spec.loader is None:
        print("[gitlab-fallback-local] Cannot load gitlab_agent.py", file=sys.stderr)
        return 1
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    ctx = {"targetApp": app, "runId": run_id}
    print(f"[gitlab-fallback-local] Publishing via GitLab MCP (local run_publish)...")
    _summary, handoff = mod.run_publish(app, ctx, root=root)
    handoff_status = handoff.get("status")
    if handoff_status == "published":
        branch_url = handoff.get("branchUrl") or "(unknown)"
        print(f"[gitlab-fallback-local] OK — branch: {branch_url}")
        return 0
    print(
        f"[gitlab-fallback-local] Publish status: {handoff_status} — error: {handoff.get('error')}",
        file=sys.stderr,
    )
    return 1


def _run_gitlab_fallback(app: str, run_id: str, timeout: int) -> int:
    """Cloud gitlab-agent first; local publish fallback if cloud fails."""
    print(f"[gitlab-fallback] GitLab handoff missing for run {run_id}. Running fallback publish.")
    cloud_code = _run_gitlab_fallback_cloud(app, run_id, timeout)
    if cloud_code == 0 and _gitlab_handoff_exists(run_id, app):
        print("[gitlab-fallback] Cloud gitlab-agent succeeded.")
        return 0
    print("[gitlab-fallback] Cloud gitlab-agent failed or produced no handoff — trying local publish...")
    local_code = _run_gitlab_fallback_local(app, run_id)
    if local_code == 0:
        return 0
    print("[gitlab-fallback] Local publish also failed (non-fatal — artifacts remain in S3).", file=sys.stderr)
    return local_code


def _build_task(
    *,
    target_app: str,
    run_id: str,
    input_file: str,
    transport: str = "a2a",
    skip_product: bool = False,
    skip_architect: bool = False,
    skip_db: bool = False,
    skip_postgres: bool = False,
    skip_developer: bool = False,
    skip_gitlab: bool = False,
    skip_verify: bool = True,
) -> str:
    payload = {
        "target_app": target_app,
        "run_id": run_id,
        "input_file": input_file,
        "transport": transport,
        "skip_product": skip_product,
        "skip_architect": skip_architect,
        "skip_db": skip_db,
        "skip_postgres": skip_postgres,
        "skip_developer": skip_developer,
        "skip_gitlab": skip_gitlab,
        "skip_verify": skip_verify,
    }
    return "Run run_sdlc_pipeline with:\n\n" + json.dumps(payload, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Invoke orchestrator pipeline on AgentCore",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--app", required=True, help="Target app name (matches inputs/<app>.txt)")
    parser.add_argument("--run-id", required=True, help="Pipeline run ID (e.g. smoke-2)")
    parser.add_argument("--input-file", default="", help="Override input file path in S3 run prefix")
    parser.add_argument("--timeout", type=int, default=900)

    parser.add_argument(
        "--full",
        action="store_true",
        help="Run product+architect+database+in-cloud RDS only (skips developer/gitlab/verify)",
    )

    parser.add_argument("--skip-product", action="store_true")
    parser.add_argument("--skip-architect", action="store_true")
    parser.add_argument("--skip-db", action="store_true", default=False)
    parser.add_argument("--no-skip-db", action="store_false", dest="skip_db")
    parser.add_argument(
        "--skip-postgres",
        action="store_true",
        default=False,
        help="Skip in-cloud RDS apply in orchestrator (use with --apply-rds-local for laptop fallback)",
    )
    parser.add_argument("--no-skip-postgres", action="store_false", dest="skip_postgres")
    parser.add_argument(
        "--apply-rds-local",
        action="store_true",
        default=False,
        help="After orchestrator, pull SQL from S3 and run apply_sql_to_rds.py on this machine (dev fallback)",
    )
    parser.add_argument("--no-apply-rds-local", action="store_false", dest="apply_rds_local")
    parser.add_argument("--skip-developer", action="store_true", default=False)
    parser.add_argument("--no-skip-developer", action="store_false", dest="skip_developer")
    parser.add_argument("--skip-gitlab", action="store_true", default=False)
    parser.add_argument("--no-skip-gitlab", action="store_false", dest="skip_gitlab")
    parser.add_argument("--skip-verify", action="store_true", default=True)
    parser.add_argument("--no-skip-verify", action="store_false", dest="skip_verify")
    args = parser.parse_args()

    _resolve_artifact_bucket()

    if args.full:
        args.skip_product = False
        args.skip_architect = False
        args.skip_db = False
        args.skip_postgres = False
        args.apply_rds_local = False
        args.skip_developer = True
        args.skip_gitlab = True
        args.skip_verify = True

    input_file = args.input_file
    if not input_file and not args.skip_product:
        input_file = _upload_input_brief(args.app, args.run_id)

    task = _build_task(
        target_app=args.app,
        run_id=args.run_id,
        input_file=input_file or f"inputs/{args.app}.txt",
        skip_product=args.skip_product,
        skip_architect=args.skip_architect,
        skip_db=args.skip_db,
        skip_postgres=args.skip_postgres,
        skip_developer=args.skip_developer,
        skip_gitlab=args.skip_gitlab,
        skip_verify=args.skip_verify,
    )

    print("Invoking orchestrator-agent...")
    print(task)
    if args.apply_rds_local and not args.skip_db and args.skip_postgres:
        print("Note: skip_postgres=True — RDS apply will run locally after orchestrator.")
    elif not args.skip_postgres and not args.skip_db:
        print("Note: skip_postgres=False — orchestrator will apply RDS in-cloud after database-agent.")
    print("---")

    if not args.skip_gitlab:
        _update_run_json(args.run_id, status="running", current_step="product-agent")

    result = invoke_agent_runtime_a2a("orchestrator-agent", task, timeout=args.timeout)
    print("status:", result.get("status"))
    if result.get("error"):
        print("error:", result.get("error"))
    text = result.get("text") or ""
    if not text and result.get("response"):
        text = extract_text_from_a2a_jsonrpc(result["response"])
    print("--- response ---")
    print(text[:8000])

    # Step 1: RDS apply (local fallback when skip_postgres=True)
    if args.apply_rds_local and not args.skip_db and args.skip_postgres:
        print("--- apply-rds-local ---")
        _update_run_json(args.run_id, current_step="database-agent")
        code = _apply_rds_local(args.app, args.run_id)
        if code != 0:
            print(f"[apply-rds-local] FAILED (exit {code})", file=sys.stderr)
            _update_run_json(args.run_id, status="failed", error="local RDS apply failed")
            raise SystemExit(code)
        print("[apply-rds-local] OK")

    # Step 2: GitLab publish fallback
    # If the orchestrator completed gitlab normally, the handoff exists in S3.
    # If developer-agent timed out (AgentCore ~15 min sync limit), the orchestrator
    # never reached gitlab — so we invoke gitlab-agent separately to push whatever
    # artifacts exist. This is non-fatal: if it fails, artifacts remain in S3.
    if not args.skip_gitlab:
        print("--- gitlab ---")
        if _gitlab_handoff_exists(args.run_id, args.app):
            print("[gitlab] Handoff already exists — orchestrator published. Skipping fallback.")
        else:
            _update_run_json(args.run_id, current_step="gitlab-agent")
            gl_code = _run_gitlab_fallback(args.app, args.run_id, args.timeout)
            if gl_code != 0:
                print(
                    f"[gitlab] Fallback publish failed (exit {gl_code}) — non-fatal. "
                    f"Run manually: python scripts/invoke-orchestrator-smoke.py "
                    f"--app {args.app} --run-id {args.run_id} --skip-product --skip-architect "
                    f"--skip-db --skip-developer",
                    file=sys.stderr,
                )

    # Step 3: Reconcile step statuses from S3 artifacts
    _reconcile_run_steps(args.run_id, args.app, args.skip_gitlab)

    # Step 4: Finalize run status based on gitlab handoff STATUS (not just existence)
    gitlab_status = _gitlab_handoff_status(args.run_id)
    orch_status = result.get("status")
    orch_text_lower = text.lower()

    if gitlab_status == "published":
        _update_run_json(args.run_id, status="completed")
    elif gitlab_status == "failed":
        gl_handoff = _get_handoff_safe(args.run_id) or {}
        gl_error = gl_handoff.get("error") or "gitlab publish failed"
        _update_run_json(args.run_id, status="failed", error=gl_error)
    elif orch_status == "success" and "pipeline failed" not in orch_text_lower:
        if not args.skip_gitlab:
            # Orchestrator succeeded but no gitlab handoff — fallback should have run
            _update_run_json(
                args.run_id,
                status="failed",
                error="gitlab handoff missing after orchestrator + fallback",
            )
        else:
            _update_run_json(args.run_id, status="completed")
    else:
        _update_run_json(
            args.run_id,
            status="failed",
            error="orchestrator did not complete — check CloudWatch logs",
        )


if __name__ == "__main__":
    main()