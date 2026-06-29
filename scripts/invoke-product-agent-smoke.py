"""One-off smoke invoke for product-agent AgentCore runtime."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "agents"))

from _shared.agentcore_invoke import extract_text_from_a2a_jsonrpc, invoke_agent_runtime_a2a

TASK = (
    "Create PRD from staged input for inventory-app.\n\n"
    "Context:\n"
    + json.dumps(
        {
            "targetApp": "inventory-app",
            "runId": "smoke-001",
            "inputFile": "inputs/inventory-app.txt",
        },
        indent=2,
    )
)


def main() -> None:
    result = invoke_agent_runtime_a2a("product-agent", TASK, timeout=600)
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
