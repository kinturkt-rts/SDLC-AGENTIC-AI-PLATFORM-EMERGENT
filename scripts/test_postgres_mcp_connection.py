"""Smoke-test: AWS Postgres MCP → RDS.

Runs the direct MCP test (no Bedrock). For full database-agent test, run:
  python agents/database-agent/database_agent.py --with-postgres --task "..."

Usage (from repo root):
  aws sso login --profile eks-admin-user
  python scripts/test_postgres_mcp_connection.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DIRECT = _REPO_ROOT / "scripts" / "test_postgres_mcp_direct.py"


def main() -> int:
    if not _DIRECT.is_file():
        print(f"ERROR: missing {_DIRECT}", file=sys.stderr)
        return 1
    print("Running direct Postgres MCP test (no Bedrock)...", file=sys.stderr)
    return subprocess.run([sys.executable, str(_DIRECT)], cwd=_REPO_ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
