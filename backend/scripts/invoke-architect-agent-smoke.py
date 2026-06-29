"""Smoke invoke for architect-agent AgentCore runtime (requires product-agent outputs in S3)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "agents"))

from _shared.agentcore_invoke import extract_text_from_a2a_jsonrpc, invoke_agent_runtime_a2a


def _build_task(target_app: str, run_id: str) -> str:
    context = {
        "targetApp": target_app,
        "runId": run_id,
        "prdPath": f"docs/PRD/{target_app}.md",
        "designDocPath": f"docs/design/{target_app}.md",
        "diagramPaths": [f"docs/diagrams/generated-diagrams/{target_app}.png"],
    }
    return (
        f"Produce architecture diagram and design doc for {target_app} MVP.\n\n"
        f"Context:\n{json.dumps(context, indent=2)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Invoke architect-agent on AgentCore")
    parser.add_argument("--app", default="bug-deduper", help="Target app slug")
    parser.add_argument("--run-id", default="smoke-002", help="Pipeline runId (S3 prefix)")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    result = invoke_agent_runtime_a2a(
        "architect-agent",
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
    print(text[:4000])


if __name__ == "__main__":
    main()
