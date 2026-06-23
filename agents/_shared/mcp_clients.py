"""Shared MCP factories for agents and Cursor"""

from __future__ import annotations

import os
import shutil
import shlex
from collections.abc import Callable
from pathlib import Path

from mcp import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp import MCPClient

AWS_DIAGRAM_MCP_VERSION = os.getenv("AWS_DIAGRAM_MCP_VERSION", "1.0.23")

ATLASSIAN_MCP_URL = os.getenv(
    "ATLASSIAN_MCP_URL",
    "https://mcp.atlassian.com/v1/mcp/authv2",
)
POSTGRES_MCP_VERSION = os.getenv("POSTGRES_MCP_VERSION", "latest")
_POSTGRES_MCP_DEFAULT_BINARY = (
    "awslabs.postgres-mcp-server.exe" if os.name == "nt" else "awslabs.postgres-mcp-server"
)
POSTGRES_MCP_BINARY = os.getenv("POSTGRES_MCP_BINARY", _POSTGRES_MCP_DEFAULT_BINARY)
MONGODB_MCP_COMMAND = os.getenv("MONGODB_MCP_COMMAND", "npx")
MONGODB_MCP_ARGS = os.getenv("MONGODB_MCP_ARGS", "-y mongodb-mcp-server")
FIRECRAWL_MCP_COMMAND = os.getenv("FIRECRAWL_MCP_COMMAND", "npx")
FIRECRAWL_MCP_ARGS = os.getenv("FIRECRAWL_MCP_ARGS", "-y firecrawl-mcp")
PLAYWRIGHT_MCP_COMMAND = os.getenv("PLAYWRIGHT_MCP_COMMAND", "npx")
PLAYWRIGHT_MCP_ARGS = os.getenv(
    "PLAYWRIGHT_MCP_ARGS",
    "-y @playwright/mcp@latest --headless --isolated",
)
POSTMAN_MCP_URL = os.getenv("POSTMAN_MCP_URL", "https://mcp.postman.com/mcp")


def firecrawl_api_key() -> str:
    """Resolve Firecrawl API key from env (.env supports FIRECRAWL_API_KEY or Firecrawl_API_Key)."""
    for key in ("FIRECRAWL_API_KEY", "Firecrawl_API_Key", "FIRECRAWL_APIKEY"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    raise ValueError(
        "FIRECRAWL_API_KEY is not set. Add it to .env or .env.local "
        "(Firecrawl_API_Key is also accepted)."
    )


def supabase_mcp_client() -> MCPClient:
    """Supabase MCP Server — hosted Postgres via Supabase Management API."""
    access_token = os.getenv("SUPABASE_ACCESS_TOKEN", "").strip()
    if not access_token:
        raise ValueError(
            "SUPABASE_ACCESS_TOKEN is not set. "
            "Get it from supabase.com/dashboard/account/tokens"
        )

    def transport() -> object:
        return stdio_client(
            StdioServerParameters(
                command="npx",
                args=[
                    "-y",
                    "@supabase/mcp-server-supabase@latest",
                    "--access-token",
                    access_token,
                ],
                env={**os.environ},
            )
        )

    return MCPClient(transport, prefix="supabase", startup_timeout=90)


def postgres_mcp_wire_method() -> str:
    """Map POSTGRES_MCP_CONNECTION_METHOD env to MCP tool enum (pgwire | pgwire_iam | rdsapi)."""
    raw = os.getenv("POSTGRES_MCP_CONNECTION_METHOD", "PG_WIRE_PROTOCOL").upper()
    if raw in ("PG_WIRE_IAM_PROTOCOL", "PGWIRE_IAM"):
        return "pgwire_iam"
    if raw in ("RDS_API", "RDSAPI"):
        return "rdsapi"
    return "pgwire"


def postgres_mcp_cluster_identifier() -> str:
    """cluster_identifier for connect_to_database / run_query.

    Standalone RDS instances must use an empty cluster_identifier so the MCP server
    calls DescribeDBInstances (via endpoint), not DescribeDBClusters.
    """
    deployment = os.getenv("POSTGRES_MCP_DEPLOYMENT", "instance").strip().lower()
    db_type = os.getenv("POSTGRES_MCP_DB_TYPE", "RPG").strip().upper()
    if deployment in ("instance", "standalone", "rds_instance"):
        return ""
    if db_type == "APG" or deployment in ("aurora", "cluster", "rds_cluster"):
        return os.getenv(
            "POSTGRES_MCP_CLUSTER_IDENTIFIER",
            os.getenv("POSTGRES_MCP_INSTANCE_IDENTIFIER", ""),
        ).strip()
    return ""


def postgres_mcp_tool_params() -> dict[str, str | int]:
    """Shared args for Postgres MCP connect_to_database and run_query tools."""
    region = os.getenv("POSTGRES_MCP_REGION", os.getenv("AWS_REGION", "us-east-2")).strip()
    endpoint = os.getenv("POSTGRES_MCP_DB_ENDPOINT", "").strip()
    database = os.getenv("POSTGRES_MCP_DATABASE", "").strip()
    db_type = os.getenv("POSTGRES_MCP_DB_TYPE", "RPG").strip().upper()
    if db_type not in ("APG", "RPG"):
        db_type = "RPG"
    port_raw = os.getenv("POSTGRES_MCP_PORT", "5432").strip()
    try:
        port = int(port_raw)
    except ValueError:
        port = 5432
    return {
        "region": region,
        "database_type": db_type,
        "connection_method": postgres_mcp_wire_method(),
        "cluster_identifier": postgres_mcp_cluster_identifier(),
        "db_endpoint": endpoint,
        "port": port,
        "database": database,
    }


def postgres_mcp_server_args() -> list[str]:
    """CLI args for awslabs.postgres-mcp-server (must match .cursor/mcp.json)."""
    method = os.getenv("POSTGRES_MCP_CONNECTION_METHOD", "PG_WIRE_PROTOCOL").strip()
    endpoint = os.getenv("POSTGRES_MCP_DB_ENDPOINT", "").strip()
    database = os.getenv("POSTGRES_MCP_DATABASE", "").strip()
    region = os.getenv("POSTGRES_MCP_REGION", os.getenv("AWS_REGION", "us-east-2")).strip()
    port = os.getenv("POSTGRES_MCP_PORT", "5432").strip()
    cluster_arn = os.getenv("POSTGRES_MCP_DB_CLUSTER_ARN", "").strip()
    db_type = os.getenv("POSTGRES_MCP_DB_TYPE", "RPG").strip()
    allow_write = os.getenv("POSTGRES_MCP_ALLOW_WRITE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }

    args = [
        "tool",
        "run",
        "--from",
        f"awslabs.postgres-mcp-server@{POSTGRES_MCP_VERSION}",
        POSTGRES_MCP_BINARY,
        "--connection_method",
        method,
        "--region",
        region,
    ]
    if method == "RDS_API":
        if not cluster_arn:
            raise ValueError("POSTGRES_MCP_DB_CLUSTER_ARN is required when connection method is RDS_API")
        args.extend(["--db_cluster_arn", cluster_arn, "--db_type", db_type])
    else:
        if not endpoint:
            raise ValueError("POSTGRES_MCP_DB_ENDPOINT is required for PG_WIRE_* connection methods")
        args.extend(["--db_endpoint", endpoint, "--port", port])
    if database:
        args.extend(["--database", database])
    if allow_write:
        args.append("--allow_write_query")
    return args


def atlassian_mcp_client() -> MCPClient:
    """Stdio via mcp-remote — matches Cursor atlassian MCP (OAuth)."""

    def transport() -> object:
        return stdio_client(
            StdioServerParameters(
                command="npx",
                args=["-y", "mcp-remote@latest", ATLASSIAN_MCP_URL],
            )
        )

    return MCPClient(transport, prefix="atlassian", startup_timeout=120)


def github_personal_access_token() -> str:
    for key in ("GITHUB_PERSONAL_ACCESS_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    raise ValueError(
        "GITHUB_PERSONAL_ACCESS_TOKEN is not set. Add it to .env for GitHub MCP in agents."
    )


def github_mcp_client() -> MCPClient:
    """Stdio transport to @modelcontextprotocol/server-github (Strands agents)."""

    token = github_personal_access_token()

    def transport() -> object:
        return stdio_client(
            StdioServerParameters(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-github"],
                env={**os.environ, "GITHUB_PERSONAL_ACCESS_TOKEN": token},
            )
        )

    return MCPClient(transport, prefix="github", startup_timeout=90)

def aws_diagram_mcp_client(*, cwd: str | Path | None = None) -> MCPClient:
    """AWS Diagram MCP Server"""

    workdir = str(cwd) if cwd else os.getcwd()
    uv = shutil.which("uv") or "uv"

    def transport() -> object:
        return stdio_client(
            StdioServerParameters(
                command=uv,
                args=[
                    "tool",
                    "run",
                    "--from",
                    f"awslabs.aws-diagram-mcp-server=={AWS_DIAGRAM_MCP_VERSION}",
                    "awslabs.aws-diagram-mcp-server",
                ],
                cwd=workdir,
                env={**os.environ, "FASTMCP_LOG_LEVEL": "ERROR"},
            )
        )

    return MCPClient(transport, prefix="awsdiagram", startup_timeout=120)


def postgres_mcp_client(*, cwd: str | Path | None = None) -> MCPClient:
    """AWS Labs Postgres MCP Server (reads POSTGRES_MCP_* from env / .env)."""

    workdir = str(cwd) if cwd else os.getcwd()
    uv = shutil.which("uv") or "uv"
    repo = Path(workdir)
    entry = repo / "scripts" / "postgres_mcp_entry.py"
    if not entry.is_file():
        entry = Path(__file__).resolve().parents[2] / "scripts" / "postgres_mcp_entry.py"

    def transport() -> object:
        return stdio_client(
            StdioServerParameters(
                command=uv,
                args=[
                    "tool",
                    "run",
                    "--from",
                    f"awslabs.postgres-mcp-server@{POSTGRES_MCP_VERSION}",
                    "python",
                    str(entry),
                ],
                cwd=workdir,
                env={**os.environ, "FASTMCP_LOG_LEVEL": "ERROR"},
            )
        )

    return MCPClient(transport, prefix="postgres", startup_timeout=90)


def firecrawl_mcp_client(*, cwd: str | Path | None = None) -> MCPClient:
    """Firecrawl MCP Server (scrape, crawl, map, search). Requires FIRECRAWL_API_KEY."""

    api_key = firecrawl_api_key()
    workdir = str(cwd) if cwd else os.getcwd()
    args = shlex.split(FIRECRAWL_MCP_ARGS)
    if not args:
        raise ValueError("FIRECRAWL_MCP_ARGS must provide at least one arg")

    def transport() -> object:
        return stdio_client(
            StdioServerParameters(
                command=FIRECRAWL_MCP_COMMAND,
                args=args,
                cwd=workdir,
                env={**os.environ, "FIRECRAWL_API_KEY": api_key},
            )
        )

    return MCPClient(transport, prefix="firecrawl", startup_timeout=90)


def mongodb_mcp_client(*, cwd: str | Path | None = None) -> MCPClient:
    """MongoDB MCP Server."""

    workdir = str(cwd) if cwd else os.getcwd()
    args = shlex.split(MONGODB_MCP_ARGS)
    if not args:
        raise ValueError("MONGODB_MCP_ARGS must provide at least one arg")

    def transport() -> object:
        return stdio_client(
            StdioServerParameters(
                command=MONGODB_MCP_COMMAND,
                args=args,
                cwd=workdir,
                env={**os.environ},
            )
        )

    return MCPClient(transport, prefix="mongodb", startup_timeout=120)


def postman_api_key() -> str:
    """Resolve Postman API key from env (.env supports POSTMAN_API_KEY)."""
    for key in ("POSTMAN_API_KEY", "Postman_API_Key"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    raise ValueError(
        "POSTMAN_API_KEY is not set. Add it to .env for Postman MCP in agents."
    )


def playwright_mcp_client(*, cwd: str | Path | None = None) -> MCPClient:
    """Playwright MCP Server — browser automation for system/E2E checks."""

    workdir = str(cwd) if cwd else os.getcwd()
    args = shlex.split(PLAYWRIGHT_MCP_ARGS)
    if not args:
        raise ValueError("PLAYWRIGHT_MCP_ARGS must provide at least one arg")

    def transport() -> object:
        return stdio_client(
            StdioServerParameters(
                command=PLAYWRIGHT_MCP_COMMAND,
                args=args,
                cwd=workdir,
                env={**os.environ},
            )
        )

    return MCPClient(transport, prefix="playwright", startup_timeout=180)


def postman_mcp_client() -> MCPClient:
    """Postman MCP Server — collections, environments, runCollection (HTTP transport)."""

    api_key = postman_api_key()

    def transport() -> object:
        return streamablehttp_client(
            POSTMAN_MCP_URL,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    return MCPClient(transport, prefix="postman", startup_timeout=90)


MCP_FACTORIES: dict[str, Callable[[], MCPClient]] = {
    "atlassian": atlassian_mcp_client,
    "github": github_mcp_client,
    "postgres": postgres_mcp_client,
    "mongodb": mongodb_mcp_client,
    "supabase": supabase_mcp_client,
    "firecrawl": firecrawl_mcp_client,
    "playwright": playwright_mcp_client,
    "postman": postman_mcp_client,
}