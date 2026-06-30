"""Smoke invoke for orchestrator-agent AgentCore runtime (deterministic pipeline)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "agents"))

from _shared.agentcore_invoke import extract_text_from_a2a_jsonrpc, invoke_agent_runtime_a2a


def _build_task(
    *,
    target_app: str,
    run_id: str,
    input_file: str,
    transport: str = "a2a",
    skip_db: bool = True,
    skip_developer: bool = True,
    skip_gitlab: bool = True,
    skip_verify: bool = True,
) -> str:
    payload = {
        "target_app": target_app,
        "run_id": run_id,
        "input_file": input_file,
        "transport": transport,
        "skip_db": skip_db,
        "skip_developer": skip_developer,
        "skip_gitlab": skip_gitlab,
        "skip_verify": skip_verify,
    }
    return "Run run_sdlc_pipeline with:\n\n" + json.dumps(payload, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Invoke orchestrator pipeline on AgentCore")
    parser.add_argument("--app", default="team-faq-bot")
    parser.add_argument("--run-id", default="smoke-004")
    parser.add_argument("--input-file", default="")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    input_file = args.input_file or f"inputs/{args.app}.txt"
    task = _build_task(
        target_app=args.app,
        run_id=args.run_id,
        input_file=input_file,
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
