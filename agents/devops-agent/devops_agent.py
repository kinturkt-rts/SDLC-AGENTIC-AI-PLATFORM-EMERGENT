"""DevOps agent — Strands + GitLab MCP + A2A."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents._shared.runner import entrypoint

AGENT_NAME = "devops-agent"

DEVOPS_SYS_PROMPT = """\
You are the DevOps Agent. Manage CI/CD and infrastructure changes using GitLab MCP.
Propose Terraform changes consistent with infrastructure/ modules. Document rollout steps.\
"""

if __name__ == "__main__":
    entrypoint(
        AGENT_NAME,
        system_prompt=DEVOPS_SYS_PROMPT,
        mcp_names=("gitlab",),
        default_port=9105,
    )
