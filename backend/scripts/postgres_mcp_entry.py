"""Postgres MCP stdio entry with optional env-based credentials"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.env import load_repo_env

load_repo_env()


def _apply_credential_patch() -> None:
    from awslabs.postgres_mcp_server.connection import psycopg_pool_connection
    import awslabs.postgres_mcp_server.server as mcp_server_module

    original_validate = mcp_server_module.validate_secret_arn_at_startup
    def _validate_secret_arn_at_startup(secret_arn: str, region: str | None) -> None:
        if secret_arn == "dummy-arn-for-local-env":
            return
        return original_validate(secret_arn, region)
    mcp_server_module.validate_secret_arn_at_startup = _validate_secret_arn_at_startup

    original = psycopg_pool_connection.PsycopgPoolConnection._get_credentials_from_secret

    def _get_credentials_from_secret(
        self,
        secret_arn: str,
        region: str,
        is_test: bool = False,
    ):
        if is_test:
            return original(self, secret_arn, region, is_test)

        if secret_arn == "dummy-arn-for-local-env":
            secret_arn = ""

        override_arn = os.environ.get("POSTGRES_MCP_SECRET_ARN", "").strip()
        if not secret_arn and override_arn:
            secret_arn = override_arn

        env_password = os.environ.get("POSTGRES_MCP_DB_PASSWORD", "").strip()
        if not secret_arn and env_password:
            env_user = os.environ.get("POSTGRES_MCP_DB_USER", "").strip()
            user = env_user or self.user or "postgres"
            return user, env_password

        return original(self, secret_arn, region, is_test)

    psycopg_pool_connection.PsycopgPoolConnection._get_credentials_from_secret = (
        _get_credentials_from_secret
    )

def _apply_ssl_patch() -> None:
    """RDS PostgreSQL expects TLS; upstream conninfo omits sslmode."""
    from psycopg_pool import AsyncConnectionPool

    original_init = AsyncConnectionPool.__init__

    def _init_with_ssl(self, conninfo: str, *args, **kwargs):
        sslmode = os.environ.get("POSTGRES_MCP_SSLMODE", "require").strip().lower()
        if sslmode and sslmode != "disable" and "sslmode=" not in conninfo:
            conninfo = f"{conninfo} sslmode={sslmode}"
        if "password=" in conninfo and "#" in conninfo:
            try:
                from psycopg.conninfo import conninfo_to_dict, make_conninfo

                params = conninfo_to_dict(conninfo)
                if params.get("password") and "#" in str(params["password"]):
                    conninfo = make_conninfo(**params)
            except Exception:
                pass
        original_init(self, conninfo, *args, **kwargs)

    AsyncConnectionPool.__init__ = _init_with_ssl  # type: ignore[method-assign]


def main() -> None:
    _apply_credential_patch()
    _apply_ssl_patch()
    
    if os.environ.get("POSTGRES_MCP_DB_PASSWORD") and "--secret_arn" not in sys.argv:
        sys.argv.extend(["--secret_arn", "dummy-arn-for-local-env"])
        
    allow_write = os.environ.get("POSTGRES_MCP_ALLOW_WRITE", "").strip().lower() in {"1", "true", "yes"}
    if allow_write and "--allow_write_query" not in sys.argv:
        sys.argv.append("--allow_write_query")
        
    from awslabs.postgres_mcp_server.server import main as mcp_main

    mcp_main()

if __name__ == "__main__":
    main()