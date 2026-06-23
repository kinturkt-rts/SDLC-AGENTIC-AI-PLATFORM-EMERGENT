"""GitLab environment configuration for gitlab-agent and jmrplens MCP."""

from __future__ import annotations

import os

_DEFAULT_API_URL = "https://code.junodev.net/api/v4"
_DEFAULT_PROJECT_PATH = "junolabs/sdlc-agentic-ai-platform/sdlc-agentic-ai-platform"


def gitlab_personal_access_token() -> str:
    for key in ("GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_TOKEN", "GL_TOKEN"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    raise ValueError(
        "GITLAB_PERSONAL_ACCESS_TOKEN is not set. Add a GitLab PAT to .env "
        "(scopes: api, read_api, read_repository, write_repository)."
    )


def gitlab_api_url() -> str:
    return (os.getenv("GITLAB_API_URL") or _DEFAULT_API_URL).strip().rstrip("/")


def gitlab_project_path() -> str:
    return (
        os.getenv("GITLAB_PROJECT_PATH")
        or os.getenv("GITLAB_PROJECT_ID")
        or _DEFAULT_PROJECT_PATH
    ).strip()


def gitlab_base_branch() -> str:
    return (os.getenv("GITLAB_BASE_BRANCH") or "main").strip() or "main"
