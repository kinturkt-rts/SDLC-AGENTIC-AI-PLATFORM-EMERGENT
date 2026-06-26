"""Orchestrator — Strands + A2A peer tools."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents._shared.runner import entrypoint

AGENT_NAME = "orchestrator-agent"

ORCHESTRATOR_SYS_PROMPT = """\
You are the Orchestrator Agent for the Autonomous SDLC platform. You receive work items,
decide which specialist agent should handle them, and coordinate hand-offs using A2A tools
(a2a_send_message, a2a_list_discovered_agents). Prefer delegating to product-agent,
architect-agent, database-agent, developer-agent, qa-agent, devops-agent, security-agent, or product-agent (Jira).
Return a short plan and the delegation results.\
"""

if __name__ == "__main__":
    entrypoint(
        AGENT_NAME,
        system_prompt=ORCHESTRATOR_SYS_PROMPT,
        mcp_names=(),
        default_port=9100,
    )
