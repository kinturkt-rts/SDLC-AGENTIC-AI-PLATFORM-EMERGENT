"""Smoke-invoke the devops_agent AgentCore runtime (standalone, not orchestrator-peered).

Usage (from backend/):
    python scripts/invoke-devops-smoke.py
    python scripts/invoke-devops-smoke.py --prompt "Generate the TF root for target app hello-fastapi"

Reads the runtime ARN from config/agentcore/runtimes.json (devops-agent entry).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.env import load_repo_env

load_repo_env()

from _shared.agentcore_invoke import extract_text_from_a2a_jsonrpc, invoke_agent_runtime_a2a

DEFAULT_PROMPT = (
    "In two sentences and without using any tools: "
    "what is your job and which tools do you have available?"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-invoke devops-agent on AgentCore")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    args = parser.parse_args()

    result = invoke_agent_runtime_a2a("devops-agent", args.prompt)
    if result.get("status") == "error":
        print(f"ERROR: {result.get('error')}")
        return 1
    print(extract_text_from_a2a_jsonrpc(result["response"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())