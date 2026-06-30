"""Smoke invoke for database-agent AgentCore runtime.

Requires product + architect outputs already in S3 under runs/<runId>/:
  docs/PRD/<app>.md
  docs/design/<app>.md
  docs/diagrams/generated-diagrams/<app>.png (optional for DB agent)

After success, verify SQL artifacts:
  aws s3 ls s3://<bucket>/runs/<runId>/target-apps/<app>/db/sql/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "agents"))

from _shared.agentcore_invoke import extract_text_from_a2a_jsonrpc, invoke_agent_runtime_a2a
from _shared.sdlc_pipeline import DB_AGENT_TASK


def _build_task(target_app: str, run_id: str) -> str:
    context = {
        "targetApp": target_app,
        "runId": run_id,
        "prdPath": f"docs/PRD/{target_app}.md",
        "designDocPath": f"docs/design/{target_app}.md",
        "diagramPaths": [f"docs/diagrams/generated-diagrams/{target_app}.png"],
        "dbOutputDir": f"target-apps/{target_app}/db",
        "preferredSqlPath": f"target-apps/{target_app}/db/sql",
    }
    return f"{DB_AGENT_TASK}\n\nContext:\n{json.dumps(context, indent=2)}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Invoke database-agent on AgentCore")
    parser.add_argument("--app", default="inventory-app", help="Target app slug")
    parser.add_argument("--run-id", default="smoke-001", help="Pipeline runId (S3 prefix)")
    parser.add_argument("--timeout", type=int, default=1200, help="Read timeout seconds")
    args = parser.parse_args()

    print(f"Invoking database-agent for {args.app} (runId={args.run_id})...")
    result = invoke_agent_runtime_a2a(
        "database-agent",
        _build_task(args.app, args.run_id),
        timeout=args.timeout,
    )
    print("status:", result.get("status"))
    if result.get("error"):
        print("error:", result.get("error"))
    text = result.get("text") or ""
    if not text and result.get("response"):
        text = extract_text_from_a2a_jsonrpc(result["response"])
    print("--- response text ---")
    print(text[:6000])
    print()
    print("Verify S3 SQL artifacts:")
    print(
        f"  aws s3 ls s3://$env:ARTIFACT_S3_BUCKET/runs/{args.run_id}/"
        f"target-apps/{args.app}/db/sql/"
    )


if __name__ == "__main__":
    main()
