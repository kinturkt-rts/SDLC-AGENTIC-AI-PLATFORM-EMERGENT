#!/usr/bin/env python3
"""Deprecated: replaced by jmrplens/gitlab-mcp-server for Cursor MCP.

Kept for reference. Cursor uses scripts/gitlab_jmrplens_stdio.py; gitlab-agent CLI
uses agents/_shared/gitlab_api.py directly.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.env import load_repo_env  # noqa: E402

load_repo_env()


def _resolve_repo_python() -> str:
    """Prefer repo .venv so Cursor's bare `python` can still start the MCP server."""
    for relative in (".venv/Scripts/python.exe", ".venv/bin/python"):
        candidate = _REPO_ROOT / relative
        if candidate.is_file():
            return str(candidate)
    return sys.executable


server = _REPO_ROOT / "scripts" / "gitlab_mcp_server.py"
argv = [_resolve_repo_python(), str(server), "--transport", "stdio"]
sys.exit(subprocess.call(argv))
