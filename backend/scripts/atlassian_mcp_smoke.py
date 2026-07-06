#!/usr/bin/env python3
"""Verify product-agent can reach Atlassian MCP (headless Basic auth or OAuth cache).

Usage (from backend/):
  python scripts/atlassian_mcp_smoke.py
  python scripts/atlassian_mcp_smoke.py --list-tools

Requires ATLASSIAN_MCP_EMAIL + ATLASSIAN_MCP_TOKEN (or ATLASSIAN_MCP_BASIC_AUTH) in .env / .env.local.
Org admin must enable API token auth for Atlassian Rovo MCP.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "agents"))

from _shared.env import load_repo_env  # noqa: E402

load_repo_env()


def _load_product_agent():
    path = _REPO / "agents" / "product-agent" / "product_agent.py"
    spec = importlib.util.spec_from_file_location("product_agent_smoke", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    parser = argparse.ArgumentParser(description="Ping Atlassian MCP via product-agent transport")
    parser.add_argument("--list-tools", action="store_true", help="Print MCP tool names")
    args = parser.parse_args()

    mod = _load_product_agent()
    basic = mod._atlassian_mcp_basic_auth_value()
    url = mod._atlassian_mcp_url()
    if not basic:
        print(
            "[atlassian-mcp-smoke] No headless credentials. Set ATLASSIAN_MCP_EMAIL + "
            "ATLASSIAN_MCP_TOKEN (or ATLASSIAN_MCP_BASIC_AUTH). OAuth-only may work if "
            "~/.mcp-auth exists from a prior Cursor login.",
            file=sys.stderr,
        )
    else:
        print(f"[atlassian-mcp-smoke] Using Basic auth against {url}", file=sys.stderr)

    try:
        with mod._atlassian_mcp() as mcp:
            tools = mcp.list_tools_sync()
    except Exception as exc:
        print(f"[atlassian-mcp-smoke] FAILED: {exc}", file=sys.stderr)
        return 1

    write_tools = [
        t
        for t in tools
        if mod._is_write_tool(t)  # noqa: SLF001
    ]
    print(f"[atlassian-mcp-smoke] OK — {len(tools)} tools ({len(write_tools)} write-capable)")
    if args.list_tools:
        for tool in tools:
            name = getattr(tool, "tool_name", None) or getattr(tool, "name", str(tool))
            print(f"  - {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
