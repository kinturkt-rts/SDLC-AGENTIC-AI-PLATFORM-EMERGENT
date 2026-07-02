"""Smoke invoke for orchestrator-agent AgentCore runtime (deterministic pipeline).

Full end-to-end (product → architect → database → developer, RDS applied locally):
  python scripts/invoke-orchestrator-smoke.py --app inventory-app --run-id smoke-2 --full --no-skip-developer

Connectivity check only (skip all agent steps):
  python scripts/invoke-orchestrator-smoke.py --app inventory-app --run-id smoke-2 --skip-product --skip-architect --skip-db --skip-developer
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

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


def _build_task(
    *,
    target_app: str,
    run_id: str,
    input_file: str,
    transport: str = "a2a",
    skip_product: bool = False,
    skip_architect: bool = False,
    skip_db: bool = True,
    skip_postgres: bool = True,
    skip_developer: bool = True,
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
        help="Run product+architect+database; apply RDS locally after (skips developer/gitlab/verify)",
    )

    parser.add_argument("--skip-product", action="store_true")
    parser.add_argument("--skip-architect", action="store_true")
    parser.add_argument("--skip-db", action="store_true", default=False)
    parser.add_argument("--no-skip-db", action="store_false", dest="skip_db")
    parser.add_argument(
        "--skip-postgres",
        action="store_true",
        default=True,
        help="Skip in-cloud RDS apply in orchestrator (default: True for smoke script; use --no-skip-postgres for in-cloud apply)",
    )
    parser.add_argument("--no-skip-postgres", action="store_false", dest="skip_postgres")
    parser.add_argument(
        "--apply-rds-local",
        action="store_true",
        default=False,
        help="After orchestrator, pull SQL from S3 and run apply_sql_to_rds.py locally",
    )
    parser.add_argument("--no-apply-rds-local", action="store_false", dest="apply_rds_local")
    parser.add_argument("--skip-developer", action="store_true", default=True)
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
        args.skip_postgres = True
        args.apply_rds_local = True
        args.skip_developer = True
        args.skip_gitlab = True
        args.skip_verify = True

    if args.skip_postgres and not args.skip_db and not args.apply_rds_local:
        args.apply_rds_local = True

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

    result = invoke_agent_runtime_a2a("orchestrator-agent", task, timeout=args.timeout)
    print("status:", result.get("status"))
    if result.get("error"):
        print("error:", result.get("error"))
    text = result.get("text") or ""
    if not text and result.get("response"):
        text = extract_text_from_a2a_jsonrpc(result["response"])
    print("--- response ---")
    print(text[:8000])

    if args.apply_rds_local and not args.skip_db and args.skip_postgres:
        print("--- apply-rds-local ---")
        code = _apply_rds_local(args.app, args.run_id)
        if code != 0:
            print(f"[apply-rds-local] FAILED (exit {code})", file=sys.stderr)
            raise SystemExit(code)
        print("[apply-rds-local] OK")


if __name__ == "__main__":
    main()