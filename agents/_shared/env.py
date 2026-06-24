"""Load repo .env then .env.local.

Priority:
  1. Merge .env then .env.local into defaults for keys not already in the shell
  2. .env.local always wins for every key it defines (overrides stale shell exports
     from placeholder .env, e.g. AWS_PROFILE=your-profile, POSTGRES_MCP_* placeholders)
  3. If AWS_PROFILE is set (shell or file), do NOT load static AWS_ACCESS_KEY_ID /
     AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN from files — those expired ASIA* values
     would override SSO and break Bedrock.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

_REPO_ROOT = Path(__file__).resolve().parents[2]

_AWS_STATIC_KEYS = frozenset(
    {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
    }
)


def load_repo_env() -> None:
    merged: dict[str, str | None] = {}
    for path in (_REPO_ROOT / ".env", _REPO_ROOT / ".env.local"):
        if path.is_file():
            merged.update(dotenv_values(path))

    use_profile = bool(os.environ.get("AWS_PROFILE") or merged.get("AWS_PROFILE"))

    for key, value in merged.items():
        if value is None or not str(value).strip():
            continue
        if use_profile and key in _AWS_STATIC_KEYS:
            continue
        if key not in os.environ:
            os.environ[key] = str(value).strip()

    local_path = _REPO_ROOT / ".env.local"
    if local_path.is_file():
        local_vals = dotenv_values(local_path)
        use_profile = bool(
            os.environ.get("AWS_PROFILE")
            or local_vals.get("AWS_PROFILE")
            or merged.get("AWS_PROFILE")
        )
        for key, value in local_vals.items():
            if value is None or not str(value).strip():
                continue
            if use_profile and key in _AWS_STATIC_KEYS:
                continue
            os.environ[key] = str(value).strip()
