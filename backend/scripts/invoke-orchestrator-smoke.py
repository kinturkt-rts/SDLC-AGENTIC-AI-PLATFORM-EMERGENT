"""Smoke invoke for orchestrator-agent AgentCore runtime (deterministic pipeline).

Full end-to-end (product → architect → database → RDS apply):
  python scripts/invoke-orchestrator-smoke.py --app inventory-app --run-id smoke-2 --full

Connectivity check only (skip all agent steps):
  python scripts/invoke-orchestrator-smoke.py --app inventory-app --run-id smoke-2
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "agents"))

from _shared.agentcore_invoke import extract_text_from_a2a_jsonrpc, invoke_agent_runtime_a2a


def _upload_input_brief(app: str, run_id: str) -> str:
    """Upload inputs/<app>.txt to S3 under the run prefix. Returns the S3 key."""
    import boto3, os
    from _shared.env import load_repo_env
    load_repo_env()
    bucket = os.environ["ARTIFACT_S3_BUCKET"]
    local = _REPO / "inputs" / f"{app}.txt"
    if not local.is_file():
        raise FileNotFoundError(f"No input file at {local}")
    key = f"runs/{run_id}/inputs/{app}.txt"
    boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-2")).upload_file(
        str(local), bucket, key
    )
    print(f"Uploaded s3://{bucket}/{key}")
    return f"inputs/{app}.txt"


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
    skip_gitlab: bool = True,
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

    # --full: run all meaningful steps (product+architect+db+rds), skip dev/gitlab/verify
    parser.add_argument("--full", action="store_true",
                        help="Run full pipeline: product+architect+database+RDS apply (skips developer/gitlab/verify)")

    parser.add_argument("--skip-product", action="store_true")
    parser.add_argument("--skip-architect", action="store_true")
    parser.add_argument("--skip-db", action="store_true", default=False)
    parser.add_argument("--no-skip-db", action="store_false", dest="skip_db")
    parser.add_argument("--skip-postgres", action="store_true", default=False)
    parser.add_argument("--no-skip-postgres", action="store_false", dest="skip_postgres")
    parser.add_argument("--skip-developer", action="store_true", default=True)
    parser.add_argument("--no-skip-developer", action="store_false", dest="skip_developer")
    parser.add_argument("--skip-gitlab", action="store_true", default=True)
    parser.add_argument("--skip-verify", action="store_true", default=True)
    args = parser.parse_args()

    if args.full:
        args.skip_product = False
        args.skip_architect = False
        args.skip_db = False
        args.skip_postgres = False
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


if __name__ == "__main__":
    main()
