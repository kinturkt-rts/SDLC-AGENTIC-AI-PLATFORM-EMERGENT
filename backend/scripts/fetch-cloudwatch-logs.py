"""Thin CLI wrapper for the Next.js API route to call.

Reads Bedrock AgentCore CloudWatch logs and prints JSON to stdout.

Usage:
    python scripts/fetch-cloudwatch-logs.py [--agent <id>] [--run-id <id>] [--minutes <n>] [--limit <n>]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "agents"))

from _shared.cloudwatch_logs import list_cloudwatch_logs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch CloudWatch logs for AgentCore runtimes")
    parser.add_argument("--agent", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--minutes", type=int, default=None)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--region", default=None)
    args = parser.parse_args()

    try:
        entries = list_cloudwatch_logs(
            agent=args.agent,
            run_id=args.run_id,
            minutes=args.minutes,
            limit=args.limit,
            region=args.region,
        )
    except Exception as err:
        print(json.dumps({"error": str(err), "logs": [], "source": "cloudwatch"}))
        return 1

    print(json.dumps({"logs": entries, "source": "cloudwatch", "count": len(entries)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
