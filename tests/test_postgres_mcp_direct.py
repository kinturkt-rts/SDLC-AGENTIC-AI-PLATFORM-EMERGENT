#!/usr/bin/env python3
"""Manual smoke test: RDS via Postgres MCP only (no Bedrock / Strands agent).

Run directly — not part of the default pytest suite (no test_* functions).

Usage (from repo root):
  aws sso login --profile eks-admin-user
  python tests/test_postgres_mcp_direct.py
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.env import load_repo_env

load_repo_env()

from _shared.mcp_clients import postgres_mcp_client, postgres_mcp_tool_params


def _preflight_aws() -> bool:
    """Verify AWS credentials before MCP tries IAM DB auth."""
    profile = os.environ.get("AWS_PROFILE", "(not set)")
    region = os.environ.get("AWS_REGION", os.environ.get("POSTGRES_MCP_REGION", "us-east-2"))
    print(f"AWS_PROFILE={profile}  AWS_REGION={region}", file=sys.stderr)
    try:
        import boto3

        sts = boto3.client("sts", region_name=region)
        ident = sts.get_caller_identity()
        print(
            f"Caller: {ident.get('Arn', ident)}  Account={ident.get('Account')}",
            file=sys.stderr,
        )
        return True
    except Exception as exc:
        print(
            "AWS credential check FAILED — fix this before RDS IAM auth will work.\n"
            "  aws sso login --profile eks-admin-user\n"
            "  $env:AWS_PROFILE='eks-admin-user'\n"
            f"  Error: {exc}",
            file=sys.stderr,
        )
        return False


def _print_result(label: str, result: object) -> None:
    print(f"\n=== {label} ===")
    if hasattr(result, "content"):
        for block in result.content:
            text = getattr(block, "text", None) or str(block)
            print(text)
    else:
        print(result)


def main() -> int:
    print("Postgres MCP direct test (no Bedrock)", file=sys.stderr)
    if not _preflight_aws():
        return 1
    try:
        params = postgres_mcp_tool_params()
        print(
            f"MCP params: connection_method={params['connection_method']} "
            f"database_type={params['database_type']} "
            f"cluster_identifier={params['cluster_identifier']!r} "
            f"db_endpoint={params['db_endpoint']}",
            file=sys.stderr,
        )
        if not params["db_endpoint"]:
            print("POSTGRES_MCP_DB_ENDPOINT is required.", file=sys.stderr)
            return 1
        if not params["database"]:
            print("POSTGRES_MCP_DATABASE is required.", file=sys.stderr)
            return 1

        with postgres_mcp_client(cwd=_REPO_ROOT) as client:
            listed = client.list_tools_sync()
            name_map = {}
            for t in listed:
                bare = getattr(getattr(t, "mcp_tool", None), "name", None)
                if bare:
                    name_map[bare] = bare
            print("MCP tools:", ", ".join(sorted(name_map)), file=sys.stderr)

            connect_args = dict(params)
            out = client.call_tool_sync(str(uuid.uuid4()), "connect_to_database", connect_args)
            _print_result("connect_to_database", out)
            connect_text = str(out)
            if "DBClusterNotFoundFault" in connect_text:
                print(
                    "\nRoot cause: cluster_identifier was sent for a standalone RDS instance.\n"
                    "The MCP server then calls DescribeDBClusters and fails.\n"
                    "Fix: set POSTGRES_MCP_DEPLOYMENT=instance (default) and do NOT pass the\n"
                    "     instance id as cluster_identifier — only POSTGRES_MCP_DB_ENDPOINT matters.",
                    file=sys.stderr,
                )
                return 1
            if "GetRoleCredentials" in connect_text and "No access" in connect_text:
                print(
                    "\nRoot cause: AWS SSO GetRoleCredentials — No access.\n"
                    "Use IAM user credentials (aws sts get-caller-identity) or fix SSO permission set.",
                    file=sys.stderr,
                )
                return 1
            if "SecretId, value: None" in connect_text or "MasterUserSecret" in connect_text:
                print(
                    "\nRoot cause: RDS uses a self-managed master password (not Secrets Manager).\n"
                    "awslabs pgwire only auto-loads credentials from RDS MasterUserSecret.\n"
                    "Fix (pick one):\n"
                    "  A) Add to .env.local (never commit):\n"
                    "       POSTGRES_MCP_DB_USER=<master username>\n"
                    "       POSTGRES_MCP_DB_PASSWORD=<master password>\n"
                    "     (uses scripts/postgres_mcp_entry.py env fallback)\n"
                    "  B) Create a Secrets Manager secret and set POSTGRES_MCP_SECRET_ARN\n"
                    "  C) In RDS console: modify instance → manage master password in Secrets Manager\n"
                    "  D) Enable IAM DB auth + PG_WIRE_IAM_PROTOCOL (no password in SM)",
                    file=sys.stderr,
                )
                return 1
            if "pool initialization incomplete" in connect_text:
                print(
                    "\nRoot cause: MCP async pool could not connect within 30s.\n"
                    "If test_postgres_wire_direct.py already shows OK, this is usually:\n"
                    "  • Windows: async psycopg needs SelectorEventLoop (fixed in postgres_mcp_entry.py)\n"
                    "  • Or RDS network/SG (run check_rds_network.py)\n"
                    "Re-run: python tests/test_postgres_mcp_direct.py",
                    file=sys.stderr,
                )
                return 1
            if '"status": "Failed"' in connect_text:
                print("\nconnect_to_database failed — see error JSON above.", file=sys.stderr)
                return 1

            query_args = {
                "sql": "SELECT current_database() AS database_name, current_user AS db_user;",
                "connection_method": params["connection_method"],
                "cluster_identifier": params["cluster_identifier"],
                "db_endpoint": params["db_endpoint"],
                "database": params["database"],
                "region": params["region"],
            }
            out = client.call_tool_sync(str(uuid.uuid4()), "run_query", query_args)
            _print_result("run_query", out)
            text = str(out)
            if "GetRoleCredentials" in text or "No access" in text:
                print(
                    "\nHint: SSO cannot assume the IAM role for this account.\n"
                    "Use a profile/role with RDS + Secrets Manager (pgwire) or rds-db:connect (IAM).",
                    file=sys.stderr,
                )
                return 1
            if "No database connection available" in text:
                print(
                    "\nHint: connect_to_database failed above — run_query cannot run until connect succeeds.",
                    file=sys.stderr,
                )
                return 1
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    print("\nDone.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
