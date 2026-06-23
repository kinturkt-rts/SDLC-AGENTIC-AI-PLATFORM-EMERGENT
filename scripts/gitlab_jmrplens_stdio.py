#!/usr/bin/env python3
"""Cursor/IDE stdio entrypoint for jmrplens/gitlab-mcp-server (GitLab Free).

Loads repo .env, maps GITLAB_PERSONAL_ACCESS_TOKEN → GITLAB_TOKEN, and runs the
jmrplens binary from bin/ (see scripts/install-jmrplens-gitlab-mcp.ps1).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.env import load_repo_env  # noqa: E402

load_repo_env()


def _gitlab_url_from_env() -> str:
    explicit = os.getenv("GITLAB_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    api = os.getenv("GITLAB_API_URL", "").strip().rstrip("/")
    if api.endswith("/api/v4"):
        return api[: -len("/api/v4")]
    return "https://code.junodev.net"


def _resolve_binary() -> Path:
    override = os.getenv("GITLAB_MCP_SERVER_PATH", "").strip()
    if override:
        path = Path(override)
        if path.is_file():
            return path
        raise SystemExit(f"GITLAB_MCP_SERVER_PATH not found: {path}")

    for candidate in (
        _REPO_ROOT / "bin" / "gitlab-mcp-server.exe",
        _REPO_ROOT / "bin" / "gitlab-mcp-server",
    ):
        if candidate.is_file():
            return candidate

    raise SystemExit(
        "jmrplens gitlab-mcp-server binary not found. "
        "Run: .\\scripts\\install-jmrplens-gitlab-mcp.ps1"
    )


def _prepare_env() -> dict[str, str]:
    token = (
        os.getenv("GITLAB_TOKEN", "").strip()
        or os.getenv("GITLAB_PERSONAL_ACCESS_TOKEN", "").strip()
    )
    if not token:
        raise SystemExit(
            "Set GITLAB_TOKEN or GITLAB_PERSONAL_ACCESS_TOKEN in .env for GitLab MCP."
        )

    env = os.environ.copy()
    env["GITLAB_TOKEN"] = token
    env.setdefault("GITLAB_URL", _gitlab_url_from_env())
    env.setdefault("GITLAB_ENTERPRISE", "false")
    return env


def main() -> None:
    binary = _resolve_binary()
    env = _prepare_env()
    raise SystemExit(subprocess.call([str(binary)], env=env))


if __name__ == "__main__":
    main()
