#!/usr/bin/env python3
"""Sync config/agentcore/runtimes.demo.json from AWS AgentCore demo runtimes.

Does not modify config/agentcore/runtimes.json (dev).

Demo AWS names → logical pipeline keys:
  product_agent_demo      → product-agent
  architect_agent_demo    → architect-agent
  database_agent_demo     → database-agent
  developer_agent_demo    → developer-agent
  orchestrator_agent_demo → orchestrator-agent

gitlab-agent is shared: copied from config/agentcore/runtimes.json when present.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

REPO = Path(__file__).resolve().parents[1]
DEMO_CONFIG = REPO / "config" / "agentcore" / "runtimes.demo.json"
DEV_CONFIG = REPO / "config" / "agentcore" / "runtimes.json"

# aws runtime name → logical agent key used by the pipeline / load_runtime_arn
DEMO_AWS_TO_LOGICAL = {
    "product_agent_demo": "product-agent",
    "architect_agent_demo": "architect-agent",
    "database_agent_demo": "database-agent",
    "developer_agent_demo": "developer-agent",
    "orchestrator_agent_demo": "orchestrator-agent",
}


def _invoke_url(region: str, account: str, runtime_id: str) -> str:
    arn = f"arn:aws:bedrock-agentcore:{region}:{account}:runtime/{runtime_id}"
    encoded = quote(arn, safe="")
    return f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded}/invocations"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-2"))
    parser.add_argument(
        "--profile",
        default=os.getenv("AWS_PROFILE") or "eks-admin-user",
    )
    args = parser.parse_args()

    try:
        import boto3
    except ImportError:
        print("boto3 required", file=sys.stderr)
        return 1

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    control = session.client("bedrock-agentcore-control")
    sts = session.client("sts")
    account = sts.get_caller_identity()["Account"]

    runtimes = control.list_agent_runtimes(maxResults=100).get("agentRuntimes") or []
    by_name = {r["agentRuntimeName"]: r for r in runtimes}

    existing: dict = {}
    if DEMO_CONFIG.is_file():
        try:
            existing = json.loads(DEMO_CONFIG.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}

    agents: dict = dict(existing.get("agents") or {})

    for aws_name, logical in DEMO_AWS_TO_LOGICAL.items():
        rt = by_name.get(aws_name)
        if not rt:
            entry = agents.get(logical) or {}
            if not entry.get("runtimeArn"):
                agents[logical] = {
                    "deployed": False,
                    "awsName": aws_name,
                    "runtimeArn": "",
                    "invokeUrl": "",
                    "notes": "Not found in AWS yet — run deploy-agentcore-agents.ps1 -Demo",
                }
            continue
        runtime_id = rt["agentRuntimeId"]
        arn = rt.get("agentRuntimeArn") or (
            f"arn:aws:bedrock-agentcore:{args.region}:{account}:runtime/{runtime_id}"
        )
        agents[logical] = {
            "deployed": True,
            "awsName": aws_name,
            "runtimeId": runtime_id,
            "runtimeArn": arn,
            "invokeUrl": _invoke_url(args.region, account, runtime_id),
            "notes": "Demo runtime — isolated from dev *_agent names.",
        }

    # Shared GitLab agent (MCP shared; no gitlab_agent_demo for now)
    if DEV_CONFIG.is_file():
        try:
            dev = json.loads(DEV_CONFIG.read_text(encoding="utf-8"))
            gitlab = (dev.get("agents") or {}).get("gitlab-agent")
            if gitlab and gitlab.get("runtimeArn"):
                agents["gitlab-agent"] = {
                    **gitlab,
                    "notes": "SHARED with dev — GitLab MCP unchanged; demo reuses this runtime ARN.",
                }
        except json.JSONDecodeError:
            pass

    demo_bucket = os.getenv("ARTIFACT_S3_BUCKET_DEMO") or os.getenv(
        "ARTIFACT_S3_BUCKET", "sdlc-agentic-ai-app-artifacts-demo"
    )

    out = {
        "description": "Demo AgentCore runtimes (no secrets). Synced by scripts/sync-runtimes-demo.py. Dev stays in runtimes.json.",
        "environment": "demo",
        "region": args.region,
        "accountId": account,
        "mvpPipeline": [
            "orchestrator-agent",
            "product-agent",
            "architect-agent",
            "database-agent",
            "developer-agent",
            "gitlab-agent",
        ],
        "artifactStore": {
            "ARTIFACT_STORE": "s3",
            "ARTIFACT_S3_BUCKET": demo_bucket,
            "ARTIFACT_DYNAMODB_ENABLED": "false",
            "notes": "Demo artifact bucket — keep separate from sdlc-agentic-ai-app-artifacts.",
        },
        "agents": agents,
    }

    DEMO_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    DEMO_CONFIG.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {DEMO_CONFIG}")
    deployed = [k for k, v in agents.items() if v.get("deployed")]
    print(f"Deployed demo/shared entries: {', '.join(deployed) or '(none yet)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
