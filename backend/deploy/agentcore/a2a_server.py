"""Single AgentCore A2A entrypoint for all SDLC agents.

Select the agent via AGENTCORE_AGENT (env) or --agent (CLI).
Agent logic lives in agents/<name>/*_agent.py; this file only adapts
local serve_a2a() to AgentCore Runtime (0.0.0.0:9000, FastAPI, serve_at_root).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_DEPLOY = Path(__file__).resolve().parent
if str(_DEPLOY) not in sys.path:
    sys.path.insert(0, str(_DEPLOY))

from agentcore_runtime.bootstrap import bootstrap

bootstrap()

from agentcore_runtime.bundles import BUNDLE_FACTORIES
from agentcore_runtime.serve import run_bundle


def _resolve_agent_name(cli_agent: str | None) -> str:
    name = (cli_agent or os.getenv("AGENTCORE_AGENT", "")).strip()
    if not name:
        known = ", ".join(sorted(BUNDLE_FACTORIES))
        raise SystemExit(
            "Set AGENTCORE_AGENT or pass --agent.\n"
            f"Known agents: {known}"
        )
    if name not in BUNDLE_FACTORIES:
        known = ", ".join(sorted(BUNDLE_FACTORIES))
        raise SystemExit(f"Unknown agent {name!r}. Known agents: {known}")
    return name


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AgentCore A2A server for SDLC agents (port 9000)",
    )
    parser.add_argument(
        "--agent",
        help="Agent registry name (e.g. architect-agent). Overrides AGENTCORE_AGENT.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Local bind port (default 9000). AgentCore deploy always uses 9000.",
    )
    args = parser.parse_args()

    if args.port is not None:
        os.environ["AGENTCORE_A2A_PORT"] = str(args.port)

    agent_name = _resolve_agent_name(args.agent)
    run_bundle(BUNDLE_FACTORIES[agent_name]())


if __name__ == "__main__":
    main()