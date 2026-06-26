#!/usr/bin/env python3
"""Cursor/IDE stdio entrypoint for awslabs.postgres-mcp-server.

Cursor ${env:VAR} in mcp.json args does not read envFile — this script loads
.env + .env.local (same as database-agent) then execs uv with POSTGRES_MCP_* args.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.env import load_repo_env
from _shared.mcp_clients import POSTGRES_MCP_VERSION

load_repo_env()

uv = shutil.which("uv") or "uv"
entry = _REPO_ROOT / "scripts" / "postgres_mcp_entry.py"
argv = [
    uv,
    "tool",
    "run",
    "--from",
    f"awslabs.postgres-mcp-server@{POSTGRES_MCP_VERSION}",
    "python",
    str(entry),
]
sys.exit(subprocess.call(argv))
