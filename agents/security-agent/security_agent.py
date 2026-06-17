"""Security agent - Strands + A2A."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents._shared.runner import entrypoint

AGENT_NAME = "security-agent"

SECURITY_SYS_PROMPT = """\
You are the Security Agent. Review code and dependencies for vulnerabilities, secrets,
and compliance gaps. Return prioritized findings with remediation steps. Use A2A to
request fixes from developer-agent when appropriate.\
"""

if __name__ == "__main__":
    entrypoint(
        AGENT_NAME,
        system_prompt=SECURITY_SYS_PROMPT,
        mcp_names=(),
        default_port=9106,
    )
