"""
scripts/test_db_mcp.py
----------------------
Verify Supabase and RDS Postgres MCP connectivity and list all available tools.

Usage:
    python scripts/test_db_mcp.py --postgres
    python scripts/test_db_mcp.py --postgres --list-tools
    python scripts/test_db_mcp.py --supabase
    python scripts/test_db_mcp.py --supabase --postgres
    python scripts/test_db_mcp.py --supabase --query "SELECT current_database(), version();"
    python scripts/test_db_mcp.py --supabase --list-tools
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "agents"))
from _shared.env import load_repo_env

load_repo_env()


def _divider(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def _tool_name(tool: Any) -> str:
    """Extract tool name from a Strands MCPAgentTool regardless of internal structure."""
    # Strands MCPAgentTool: name lives on tool_spec.name
    spec = getattr(tool, "tool_spec", None)
    if spec is not None:
        n = getattr(spec, "name", None)
        if n:
            return str(n)
        # spec may be a dict (older strands versions)
        if isinstance(spec, dict):
            return str(spec.get("name", ""))

    # Fallback: check direct .name attribute (some wrapper versions)
    direct = getattr(tool, "name", None)
    if direct and not str(direct).startswith("<"):
        return str(direct)

    # Last resort: str(tool) sometimes includes the name
    return str(tool)


def _tool_desc(tool: Any) -> str:
    spec = getattr(tool, "tool_spec", None)
    if spec is not None:
        d = getattr(spec, "description", None) or (spec.get("description", "") if isinstance(spec, dict) else "")
        if d:
            return str(d).strip().split("\n")[0][:80]
    return getattr(tool, "description", "") or ""


def _print_tools(tools: list[Any]) -> None:
    if not tools:
        print("  (no tools returned)")
        return
    max_name = max((len(_tool_name(t)) for t in tools), default=20)
    for t in tools:
        name = _tool_name(t)
        desc = _tool_desc(t)
        if desc:
            print(f"  ✓  {name:<{max_name}}   {desc}")
        else:
            print(f"  ✓  {name}")


def _find_sql_tool(tools: list[Any]) -> Any | None:
    """Find the SQL execution tool by name keywords."""
    keywords = ("execute_sql", "run_sql", "execute_query", "run_query", "query", "sql")
    # exact name match first
    for kw in keywords:
        for t in tools:
            if _tool_name(t).lower() == kw:
                return t
    # substring match
    for kw in ("sql", "query", "execute"):
        for t in tools:
            if kw in _tool_name(t).lower():
                return t
    return None


def _call_tool(client: Any, tool: Any, args: dict[str, Any]) -> Any:
    """Call an MCP tool via the strands MCPClient."""
    name = _tool_name(tool)
    # strands MCPClient exposes call_tool_sync(tool_name, input_dict)
    if hasattr(client, "call_tool_sync"):
        return client.call_tool_sync(name, args)
    # fallback: tool is callable directly
    return tool(**args)


def test_supabase(query: str | None, list_tools: bool) -> bool:
    _divider("SUPABASE MCP")

    token = os.getenv("SUPABASE_ACCESS_TOKEN", "").strip()
    project = os.getenv("SUPABASE_PROJECT_ID", "").strip()

    if not token:
        print("  ✗  SUPABASE_ACCESS_TOKEN not set in .env")
        return False

    print(f"  Token      : ...{token[-6:]} (last 6 chars)")
    print(f"  Project ID : {project or '(not set — server will list all projects)'}")

    try:
        from _shared.mcp_clients import supabase_mcp_client
    except ImportError:
        print("  ✗  supabase_mcp_client missing from mcp_clients.py")
        return False

    print("\n  Starting Supabase MCP server ...")
    try:
        with supabase_mcp_client() as client:
            tools = client.list_tools_sync()
            names = [_tool_name(t) for t in tools]

            print(f"\n  Connected ✓   {len(tools)} tools available\n")
            _print_tools(tools)

            # ── optional: run a SQL query ──────────────────────────────────
            if query:
                print(f"\n  SQL query: {query}")
                sql_tool = _find_sql_tool(tools)
                if not sql_tool:
                    print(f"\n  Available tool names: {names}")
                    print("  ✗  No SQL tool found. Check tool names above.")
                    return True   # still connected, just no matching tool

                tool_name = _tool_name(sql_tool)
                print(f"  Using tool : {tool_name}")

                # Supabase MCP uses project_id + query params
                call_args: dict[str, Any] = {"query": query}
                if project:
                    call_args["project_id"] = project

                result = _call_tool(client, sql_tool, call_args)
                print(f"\n  Result:\n{json.dumps(result, indent=2, default=str)}")

    except Exception as exc:
        print(f"\n  ✗  Connection failed: {exc}")
        print("  Checks: SUPABASE_ACCESS_TOKEN valid? npx on PATH? Network OK?")
        return False

    return True


def test_postgres(query: str | None, list_tools: bool) -> bool:
    _divider("AWS POSTGRES MCP (RDS)")

    endpoint = os.getenv("POSTGRES_MCP_DB_ENDPOINT", "").strip()
    region = os.getenv("POSTGRES_MCP_REGION", os.getenv("AWS_REGION", "")).strip()
    database = os.getenv("POSTGRES_MCP_DATABASE", "").strip()
    profile = os.getenv("AWS_PROFILE", "").strip()

    print(f"  Endpoint   : {endpoint or '(POSTGRES_MCP_DB_ENDPOINT not set)'}")
    print(f"  Region     : {region or '(not set)'}")
    print(f"  Database   : {database or '(not set)'}")
    print(f"  AWS Profile: {profile or '(default credential chain)'}")

    if not endpoint:
        print("\n  ✗  POSTGRES_MCP_DB_ENDPOINT is required for awslabs postgres MCP.")
        print("     Set it to your RDS hostname, e.g.:")
        print("     POSTGRES_MCP_DB_ENDPOINT=mydb.xxxx.us-east-2.rds.amazonaws.com")
        return False

    try:
        from _shared.mcp_clients import postgres_mcp_client
    except ImportError:
        print("  ✗  postgres_mcp_client missing from mcp_clients.py")
        return False

    print("\n  Starting AWS Postgres MCP server ...")
    try:
        with postgres_mcp_client(cwd=_REPO_ROOT) as client:
            tools = client.list_tools_sync()
            names = [_tool_name(t) for t in tools]

            print(f"\n  Connected ✓   {len(tools)} tools available\n")
            _print_tools(tools)

            if query:
                print(f"\n  SQL query: {query}")
                sql_tool = _find_sql_tool(tools)
                if not sql_tool:
                    print(f"\n  Available tool names: {names}")
                    print("  ✗  No SQL tool found.")
                    return True

                tool_name = _tool_name(sql_tool)
                print(f"  Using tool : {tool_name}")
                result = _call_tool(client, sql_tool, {"query": query})
                print(f"\n  Result:\n{json.dumps(result, indent=2, default=str)}")

    except Exception as exc:
        print(f"\n  ✗  Connection failed: {exc}")
        print("  Checks: uv on PATH? AWS credentials valid? RDS security group open to your IP?")
        return False

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Test DB MCP connectivity")
    parser.add_argument("--supabase", action="store_true", help="Test Supabase MCP")
    parser.add_argument("--postgres", action="store_true", help="Test AWS Postgres MCP")
    parser.add_argument("--query", help="SQL query to execute after connectivity check")
    parser.add_argument("--list-tools", action="store_true", help="Print full tool list (always on)")
    args = parser.parse_args()

    if not args.supabase and not args.postgres:
        parser.print_help()
        print("\nTip: python scripts/test_db_mcp.py --supabase --query \"SELECT version();\"")
        sys.exit(0)

    results: dict[str, bool] = {}
    if args.supabase:
        results["supabase"] = test_supabase(args.query, args.list_tools)
    if args.postgres:
        results["postgres"] = test_postgres(args.query, args.list_tools)

    _divider("SUMMARY")
    for name, ok in results.items():
        status = "✓  connected" if ok else "✗  failed"
        print(f"  {name:<12} {status}")

    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()